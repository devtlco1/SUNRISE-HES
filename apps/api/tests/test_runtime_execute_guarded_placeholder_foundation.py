from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_worker_runtime_executor_foundation import (
    _create_started_attempt,
    _login_as_super_admin,
)


def test_execute_runtime_plan_succeeds_with_matching_active_lease_and_gate(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-success",
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
    assert payload["result_summary"]["execution_guard"]["executor_identifier"] == "worker-runtime-1"

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    guard_metadata = attempt.execution_metadata["runtime_execution_guard"]
    assert guard_metadata["executor_identifier"] == "worker-runtime-1"
    assert command.result_summary["execution_guard"]["executor_identifier"] == "worker-runtime-1"
    assert job_run.result_summary["execution_guard"]["executor_identifier"] == "worker-runtime-1"


def test_execute_runtime_plan_refuses_when_no_lease_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-no-lease",
        max_retries=0,
        grant_runtime_coordination=False,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "active runtime lease" in response.json()["detail"].lower()


def test_execute_runtime_plan_refuses_when_no_invocation_gate_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-no-gate",
        max_retries=0,
    )
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("runtime_execution_invocation_gate", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "invocation gate" in response.json()["detail"].lower()


def test_execute_runtime_plan_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-lease-mismatch",
        max_retries=0,
    )
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    lease_metadata = {
        **attempt.execution_metadata["runtime_execution_lease"],
        "executor_identifier": "another-executor",
    }
    attempt.execution_metadata = {
        **attempt.execution_metadata,
        "runtime_execution_lease": lease_metadata,
    }
    db_session.add(attempt)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "lease is owned by another executor" in response.json()["detail"].lower()


def test_execute_runtime_plan_refuses_when_invocation_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-gate-mismatch",
        max_retries=0,
    )
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    invocation_metadata = {
        **attempt.execution_metadata["runtime_execution_invocation_gate"],
        "executor_identifier": "another-executor",
    }
    attempt.execution_metadata = {
        **attempt.execution_metadata,
        "runtime_execution_invocation_gate": invocation_metadata,
    }
    db_session.add(attempt)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "invocation gate is owned by another executor" in response.json()["detail"].lower()


def test_execute_runtime_plan_refuses_when_lease_is_expired(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-lease-expired",
        max_retries=0,
    )
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    lease_metadata = {
        **attempt.execution_metadata["runtime_execution_lease"],
        "lease_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat(),
    }
    attempt.execution_metadata = {
        **attempt.execution_metadata,
        "runtime_execution_lease": lease_metadata,
    }
    db_session.add(attempt)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "lease is expired" in response.json()["detail"].lower()


def test_execute_runtime_plan_refuses_when_invocation_gate_is_expired(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-gate-expired",
        max_retries=0,
    )
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    invocation_metadata = {
        **attempt.execution_metadata["runtime_execution_invocation_gate"],
        "gate_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat(),
    }
    attempt.execution_metadata = {
        **attempt.execution_metadata,
        "runtime_execution_invocation_gate": invocation_metadata,
    }
    db_session.add(attempt)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "invocation gate is expired" in response.json()["detail"].lower()


def test_repeated_execute_runtime_plan_remains_safe_after_completion(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-guarded-exec-repeat",
        max_retries=0,
    )

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "already finalized" in second.json()["detail"].lower()
