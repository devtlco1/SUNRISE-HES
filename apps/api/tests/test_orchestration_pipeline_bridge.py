from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.bootstrap import bootstrap_access_control
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


def test_prepare_eligible_scheduled_work_end_to_end(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_due_job_run(client, token)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/prepare-for-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-pipeline-1", "lease_seconds": 60},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_run_claimed"] is True
    assert payload["command_materialized"] is True
    assert payload["attempt_started"] is True
    assert payload["job_run"]["status"] == "running"
    assert payload["related_command"]["current_status"] == "in_progress"
    assert payload["created_or_existing_attempt"]["status"] == "started"


def test_repeated_prepare_returns_existing_records_without_duplication(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_due_job_run(client, token)

    first = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/prepare-for-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-pipeline-1", "lease_seconds": 60},
    )
    second = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/prepare-for-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-pipeline-1", "lease_seconds": 60},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["related_command"]["id"] == second.json()["related_command"]["id"]
    assert first.json()["created_or_existing_attempt"]["id"] == second.json()["created_or_existing_attempt"]["id"]
    assert second.json()["job_run_claimed"] is False
    assert second.json()["command_materialized"] is False
    assert second.json()["attempt_started"] is False


def test_reject_non_eligible_job_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_due_job_run(client, token)

    job_run = db_session.get(JobRun, job_run_id)
    job_run.status = "succeeded"
    db_session.add(job_run)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/prepare-for-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-pipeline-1", "lease_seconds": 60},
    )

    assert response.status_code == 409
    assert "cannot be prepared" in response.json()["detail"].lower()


def test_reject_second_concurrent_active_attempt_creation(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_due_job_run(client, token)

    first = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/prepare-for-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-pipeline-1", "lease_seconds": 60},
    )
    assert first.status_code == 200

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/prepare-for-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-pipeline-2", "lease_seconds": 60},
    )

    assert response.status_code == 409


def test_pipeline_keeps_job_command_attempt_synchronized(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_due_job_run(client, token)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/prepare-for-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-pipeline-1", "lease_seconds": 60},
    )

    assert response.status_code == 200
    payload = response.json()
    command_id = payload["related_command"]["id"]
    attempt_id = payload["created_or_existing_attempt"]["id"]

    job_run = db_session.get(JobRun, job_run_id)
    command = db_session.get(MeterCommand, command_id)
    attempt = db_session.get(CommandExecutionAttempt, attempt_id)

    assert job_run.related_command_id == command.id
    assert job_run.status == "running"
    assert command.current_status == "in_progress"
    assert attempt.meter_command_id == command.id
    assert attempt.job_run_id == job_run.id
    assert attempt.ended_at is None


def _create_due_job_run(client, token: str) -> str:
    from tests.test_scheduler_run_generation_foundation import _create_interval_job_definition_with_meter, _assign_target

    job_definition_id, meter_id = _create_interval_job_definition_with_meter(client, token)
    _assign_target(client, token, job_definition_id, meter_id)

    generation = client.post(
        "/api/v1/internal/scheduler/generate-due-runs",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "as_of": datetime.now(UTC).isoformat(),
            "window_seconds": 120,
            "job_definition_id": job_definition_id,
        },
    )
    assert generation.status_code == 200
    return generation.json()["items"][0]["id"]
