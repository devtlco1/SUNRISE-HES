from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_runtime_execution_claim_to_work_foundation import (
    _enqueue_and_claim_dispatch_message,
)
from tests.test_worker_runtime_executor_foundation import (
    _create_started_attempt,
    _login_as_super_admin,
)


def _create_runtime_handoff(
    client,
    db_session: Session,
    monkeypatch,
) -> tuple[str, dict[str, object], dict[str, object], str, object]:
    job_run_id, claim_result, stream_name, _, redis_client = _enqueue_and_claim_dispatch_message(
        client,
        db_session,
        monkeypatch,
    )
    handoff_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/runtime-handoff",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "runtime-handoff-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )
    assert handoff_response.status_code == 200
    return job_run_id, claim_result, handoff_response.json(), stream_name, redis_client


def test_runtime_execution_lease_creates_durable_executor_assignment(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, claim_result, handoff_payload, stream_name, redis_client = _create_runtime_handoff(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/lease-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["status"] == "leased"
    assert result["executor_identifier"] == "executor-a"
    assert result["command_attempt_id"] == attempt_id
    assert result["job_run_id"] == job_run_id
    assert result["related_command_id"] == handoff_payload["result"]["related_command_id"]
    assert result["reused_existing_lease"] is False
    assert result["lineage"]["handoff_record_id"] == handoff_payload["result"]["handoff_record_id"]
    assert result["lineage"]["dispatch_request_identity"] == (
        f"{job_run_id}:retry_dispatch_request"
    )
    assert result["lineage"]["queue_message_id"] == claim_result["message"]["message_id"]
    assert payload["created_or_existing_attempt"]["id"] == attempt_id
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
    lease_metadata = attempt.execution_metadata["runtime_execution_lease"]
    assert lease_metadata["executor_identifier"] == "executor-a"
    assert (
        lease_metadata["lineage"]["queue_message_id"] == claim_result["message"]["message_id"]
    )
    assert (
        job_run.result_summary["runtime_execution_lease"]["lease_record_id"]
        == result["lease_record_id"]
    )
    assert (
        command.result_summary["runtime_execution_lease"]["lease_record_id"]
        == result["lease_record_id"]
    )

    redis_client.delete(stream_name)


def test_repeated_runtime_execution_lease_reuses_active_lease_for_same_executor(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, _, handoff_payload, stream_name, redis_client = _create_runtime_handoff(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/lease-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/lease-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["result"]["lease_record_id"] == first.json()["result"]["lease_record_id"]
    assert second.json()["result"]["leased_at"] == first.json()["result"]["leased_at"]
    assert second.json()["result"]["reused_existing_lease"] is True

    redis_client.delete(stream_name)


def test_runtime_execution_lease_rejects_conflicting_active_executor(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, _, handoff_payload, stream_name, redis_client = _create_runtime_handoff(
        client,
        db_session,
        monkeypatch,
    )
    attempt_id = handoff_payload["result"]["command_attempt_id"]

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/lease-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/lease-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-b"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "active lease owned by another executor" in second.json()["detail"]

    redis_client.delete(stream_name)


def test_runtime_execution_lease_requires_existing_runtime_handoff(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-lease-no-handoff",
        max_retries=0,
        grant_runtime_coordination=False,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/lease-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "executor-a"},
    )

    assert response.status_code == 409
    assert "handoff is required" in response.json()["detail"].lower()
