from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.connectivity.enums import ConnectivitySessionPurpose, ConnectivitySessionStatus
from app.modules.connectivity.models import ConnectivitySessionHistory
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.adapters.dlms_cosem import GuruxDlmsAdapterBridge
from app.runtime.contracts import (
    RuntimeCommandOutcome,
    RuntimeCommandResult,
    RuntimeSessionResult,
)


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


def test_execute_runtime_plan_for_valid_attempt_using_placeholder_adapter(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-exec-success",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "succeeded"
    assert payload["plan"]["adapter_key"] == "gurux-dlms-bridge"
    assert payload["attempt"]["status"] == "succeeded"
    assert payload["session"]["status"] == "succeeded"

    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt is not None and attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert attempt.session_history_id is not None
    assert command is not None and command.current_status == "succeeded"
    assert job_run is not None and job_run.status == "succeeded"


def test_execute_runtime_plan_creates_and_finalizes_connectivity_session_history(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded", "bytes_sent": 144, "bytes_received": 288},
        command_template_code="runtime-exec-session",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    session_id = response.json()["session"]["id"]
    session_history = db_session.get(ConnectivitySessionHistory, session_id)
    assert session_history is not None
    assert session_history.status == ConnectivitySessionStatus.SUCCEEDED
    assert session_history.session_purpose == ConnectivitySessionPurpose.MANUAL_DIAGNOSTIC
    assert session_history.started_at is not None
    assert session_history.ended_at is not None
    assert session_history.bytes_sent == 144
    assert session_history.bytes_received == 288


def test_execute_runtime_plan_synchronizes_failure_statuses(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "MOCK_FAILURE",
            "error_message": "Placeholder adapter failure",
        },
        command_template_code="runtime-exec-failure",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "failed"
    assert payload["attempt"]["status"] == "failed"
    assert payload["session"]["status"] == "failed"

    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt is not None and attempt.status == CommandExecutionAttemptStatus.FAILED
    assert command is not None and command.current_status == "failed"
    assert job_run is not None and job_run.status == "failed"


def test_reject_execution_when_runtime_plan_context_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt_without_runtime_context(
        client,
        token,
        command_template_code="runtime-exec-missing",
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "endpoint assignment" in response.json()["detail"].lower()


def test_executor_uses_adapter_boundary(monkeypatch, client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-exec-adapter-boundary",
        max_retries=0,
    )
    called = {"used": False}

    def fake_execute(self, plan):  # noqa: ANN001
        called["used"] = True
        now = datetime.now(UTC)
        return RuntimeCommandResult(
            outcome=RuntimeCommandOutcome.SUCCEEDED,
            result_summary={"adapter": "patched"},
            response_snapshot={"adapter": "patched"},
            session_result=RuntimeSessionResult(
                status=ConnectivitySessionStatus.SUCCEEDED,
                session_purpose=plan.session_purpose,
                started_at=now,
                ended_at=now,
                bytes_sent=1,
                bytes_received=2,
            ),
        )

    monkeypatch.setattr(GuruxDlmsAdapterBridge, "execute", fake_execute)

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    assert called["used"] is True
    assert response.json()["response_snapshot"]["adapter"] == "patched"


def _create_started_attempt(
    client,
    db_session: Session,
    token: str,
    *,
    mock_execution: dict[str, object],
    command_template_code: str,
    max_retries: int,
) -> tuple[str, str, str]:
    from tests.test_jobs_scheduler_foundation import (
        _create_job_definition_record,
        _create_manual_job_run_record,
    )
    from tests.test_protocol_runtime_foundation import (
        _attach_runtime_connectivity,
        _create_meter_record,
    )

    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_record(
        client,
        token,
        command_template_code,
        max_retries=max_retries,
    )

    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_profile_id,
            "idempotency_key": f"runtime-exec-{_suffix()}",
            "request_payload": {"mock_execution": mock_execution},
        },
    )
    assert command_response.status_code == 201
    command_id = command_response.json()["id"]

    job_definition_id = _create_job_definition_record(client, token, f"runtime-job-{_suffix()}")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    claim_response = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "limit": 10, "lease_seconds": 60},
    )
    assert claim_response.status_code == 200

    start_attempt = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "meter_command_id": command_id},
    )
    assert start_attempt.status_code == 200
    return start_attempt.json()["id"], command_id, job_run_id


def _create_started_attempt_without_runtime_context(
    client,
    token: str,
    *,
    command_template_code: str,
) -> tuple[str, str, str]:
    from tests.test_jobs_scheduler_foundation import (
        _create_job_definition_record,
        _create_manual_job_run_record,
        _create_meter_record,
    )

    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, command_template_code, max_retries=0)

    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "idempotency_key": f"runtime-missing-{_suffix()}",
        },
    )
    assert command_response.status_code == 201

    job_definition_id = _create_job_definition_record(client, token, f"runtime-missing-job-{_suffix()}")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    claim_response = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "limit": 10, "lease_seconds": 60},
    )
    assert claim_response.status_code == 200

    start_attempt = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "meter_command_id": command_response.json()["id"]},
    )
    assert start_attempt.status_code == 200
    return start_attempt.json()["id"], command_response.json()["id"], job_run_id


def _create_command_template_record(client, token: str, code: str, *, max_retries: int) -> str:
    response = client.post(
        "/api/v1/command-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "name": code.replace("-", " ").title(),
            "category": "on_demand_read",
            "target_scope": "meter",
            "timeout_seconds": 120,
            "max_retries": max_retries,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _suffix() -> str:
    return str(int(datetime.now(UTC).timestamp() * 1000))
