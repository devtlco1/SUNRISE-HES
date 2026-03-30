from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_runtime_execution_lease_foundation import _create_runtime_handoff


def _create_leased_runtime_attempt(
    client,
    db_session: Session,
    monkeypatch,
) -> tuple[str, dict[str, object], dict[str, object], object]:
    job_run_id, claim_result, handoff_payload, stream_name, redis_client = _create_runtime_handoff(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]
    lease_response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/lease-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )
    assert lease_response.status_code == 200
    return job_run_id, claim_result, handoff_payload, lease_response.json(), redis_client


def test_runtime_execution_invocation_gate_authorizes_when_active_lease_matches_executor(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    (
        job_run_id,
        claim_result,
        handoff_payload,
        lease_payload,
        redis_client,
    ) = _create_leased_runtime_attempt(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/gate-execution-invocation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["status"] == "authorized"
    assert result["executor_identifier"] == "executor-a"
    assert result["command_attempt_id"] == attempt_id
    assert result["job_run_id"] == job_run_id
    assert result["lineage"]["handoff_record_id"] == handoff_payload["result"]["handoff_record_id"]
    assert result["lineage"]["lease_record_id"] == lease_payload["result"]["lease_record_id"]
    assert result["lineage"]["queue_message_id"] == claim_result["message"]["message_id"]
    assert payload["created_or_existing_attempt"]["status"] == "started"

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    command = db_session.get(
        MeterCommand,
        uuid.UUID(handoff_payload["result"]["related_command_id"]),
    )
    assert attempt is not None
    assert job_run is not None
    assert command is not None
    invocation_metadata = attempt.execution_metadata["runtime_execution_invocation_gate"]
    assert invocation_metadata["executor_identifier"] == "executor-a"
    assert (
        invocation_metadata["lineage"]["lease_record_id"]
        == lease_payload["result"]["lease_record_id"]
    )
    assert (
        job_run.result_summary["runtime_execution_invocation_gate"]["invocation_record_id"]
        == result["invocation_record_id"]
    )
    assert (
        command.result_summary["runtime_execution_invocation_gate"]["invocation_record_id"]
        == result["invocation_record_id"]
    )

    redis_client.delete(settings.redis_queue_stream_name)


def test_runtime_execution_invocation_gate_refuses_when_no_lease_exists(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, _, handoff_payload, _, redis_client = _create_runtime_handoff(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/gate-execution-invocation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )

    assert response.status_code == 409
    assert "active runtime lease" in response.json()["detail"].lower()

    redis_client.delete(settings.redis_queue_stream_name)


def test_runtime_execution_invocation_gate_refuses_for_different_executor(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, _, handoff_payload, _, redis_client = _create_leased_runtime_attempt(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/gate-execution-invocation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-b"},
    )

    assert response.status_code == 409
    assert "owned by another executor" in response.json()["detail"].lower()

    redis_client.delete(settings.redis_queue_stream_name)


def test_runtime_execution_invocation_gate_refuses_when_lease_is_expired(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, _, handoff_payload, _, redis_client = _create_leased_runtime_attempt(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    expired_at = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
    lease_metadata = {
        **attempt.execution_metadata["runtime_execution_lease"],
        "lease_expires_at": expired_at,
    }
    attempt.execution_metadata = {
        **attempt.execution_metadata,
        "runtime_execution_lease": lease_metadata,
    }
    db_session.add(attempt)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/gate-execution-invocation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )

    assert response.status_code == 409
    assert "expired" in response.json()["detail"].lower()

    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert job_run is not None
    redis_client.delete(settings.redis_queue_stream_name)


def test_runtime_execution_invocation_gate_reuses_existing_authorization_for_same_executor(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, _, handoff_payload, _, redis_client = _create_leased_runtime_attempt(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/gate-execution-invocation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/gate-execution-invocation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        second.json()["result"]["invocation_record_id"]
        == first.json()["result"]["invocation_record_id"]
    )
    assert second.json()["result"]["invoked_at"] == first.json()["result"]["invoked_at"]
    assert second.json()["result"]["reused_existing_invocation"] is True

    redis_client.delete(settings.redis_queue_stream_name)
