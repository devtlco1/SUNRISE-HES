from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun


def _login_as_super_admin(client, db_session: Session) -> str:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"
    bootstrap_access_control(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_start_command_attempt_from_claimed_job_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    command_id, job_run_id = _create_claimed_job_and_command(client, token)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "worker-a",
            "meter_command_id": command_id,
            "request_snapshot": {"step": "start"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["attempt_number"] == 1
    assert payload["status"] == "started"

    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert command.current_status == "in_progress"
    assert job_run.status == "running"


def test_reject_start_from_non_claimed_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    command_id, job_run_id = _create_job_and_command_without_claim(client, token)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-a", "meter_command_id": command_id},
    )

    assert response.status_code == 409
    assert "claimed" in response.json()["detail"].lower()


def test_succeed_path_updates_attempt_command_and_job_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    command_id, job_run_id = _create_claimed_job_and_command(client, token)
    attempt_id = _start_attempt(client, job_run_id, command_id, "worker-a")

    mark_running = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/mark-running",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-a", "execution_metadata": {"phase": "running"}},
    )
    assert mark_running.status_code == 200

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/succeed",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "worker-a",
            "response_snapshot": {"result": "ok"},
            "result_summary": {"status": "ok"},
            "bytes_sent": 128,
            "bytes_received": 512,
            "latency_ms": 44,
        },
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert attempt.ended_at is not None
    assert command.current_status == "succeeded"
    assert job_run.status == "succeeded"


def test_fail_path_updates_attempt_and_statuses(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    command_id, job_run_id = _create_claimed_job_and_command(client, token)
    attempt_id = _start_attempt(client, job_run_id, command_id, "worker-a")

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/fail",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "worker-a",
            "error_code": "NO_ROUTE",
            "error_message": "No route to device",
            "retry_delay_seconds": 10,
        },
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt.status == CommandExecutionAttemptStatus.FAILED
    assert command.current_status == "retry_wait"
    assert job_run.status == "pending"


def test_timeout_path_updates_attempt_and_statuses(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    command_id, job_run_id = _create_claimed_job_and_command(client, token)
    attempt_id = _start_attempt(client, job_run_id, command_id, "worker-a")

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/timeout",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "worker-a",
            "error_message": "Operation timed out",
            "retry_delay_seconds": 0,
        },
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt.status == CommandExecutionAttemptStatus.TIMED_OUT
    assert command.current_status == "retry_wait"
    assert job_run.status == "pending"


def test_reject_second_concurrent_active_attempt_for_same_command(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    command_id, job_run_id = _create_claimed_job_and_command(client, token)
    _start_attempt(client, job_run_id, command_id, "worker-a")

    duplicate_job_run = db_session.get(JobRun, job_run_id)
    duplicate_job_run.status = "claimed"
    duplicate_job_run.worker_identifier = "worker-a"
    duplicate_job_run.claimed_at = datetime.now(UTC)
    db_session.add(duplicate_job_run)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-a", "meter_command_id": command_id},
    )

    assert response.status_code == 409
    assert "active execution attempt" in response.json()["detail"].lower()


def _start_attempt(client, job_run_id: str, command_id: str, worker_identifier: str) -> str:
    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": worker_identifier, "meter_command_id": command_id},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_claimed_job_and_command(client, token: str) -> tuple[str, str]:
    command_id, job_run_id = _create_job_and_command_without_claim(client, token)
    claim_response = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-a", "limit": 10, "lease_seconds": 60},
    )
    assert claim_response.status_code == 200
    return command_id, job_run_id


def _create_job_and_command_without_claim(client, token: str) -> tuple[str, str]:
    from tests.test_jobs_scheduler_foundation import (
        _create_command_template_record,
        _create_job_definition_record,
        _create_manual_job_run_record,
        _create_meter_record,
    )

    meter_id = _create_meter_record(client, token)
    command_template_id = _create_command_template_record(client, token, f"bridge-template-{int(datetime.now(UTC).timestamp()*1000)}")
    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"command_template_id": command_template_id, "idempotency_key": f"bridge-cmd-{int(datetime.now(UTC).timestamp()*1000)}"},
    )
    assert command_response.status_code == 201

    job_definition_id = _create_job_definition_record(client, token, f"bridge-job-{int(datetime.now(UTC).timestamp()*1000)}")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)
    return command_response.json()["id"], job_run_id
