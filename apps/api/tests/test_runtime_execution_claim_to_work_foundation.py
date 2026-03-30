from __future__ import annotations

import uuid

from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def _build_real_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _configure_real_redis_settings(monkeypatch, *, stream_name: str, consumer_group: str) -> None:
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(settings, "redis_queue_stream_name", stream_name)
    monkeypatch.setattr(settings, "redis_queue_consumer_group_name", consumer_group)


def _enqueue_and_claim_dispatch_message(
    client,
    db_session: Session,
    monkeypatch,
) -> tuple[str, dict[str, object], str, str, Redis]:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group = f"hes-worker-group:{uuid.uuid4()}"
    _configure_real_redis_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group=consumer_group,
    )
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    enqueue_response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert enqueue_response.status_code == 200

    claim_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "runtime-handoff-worker",
            "ensure_consumer_group": True,
        },
    )

    assert claim_response.status_code == 200
    return (
        job_run_id,
        claim_response.json()["result"],
        stream_name,
        consumer_group,
        redis_client,
    )


def test_runtime_execution_handoff_creates_durable_runtime_work_from_claim(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, claim_result, stream_name, consumer_group, redis_client = (
        _enqueue_and_claim_dispatch_message(client, db_session, monkeypatch)
    )

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/runtime-handoff",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "runtime-handoff-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["status"] == "handed_off"
    assert result["stream_name"] == stream_name
    assert result["consumer_group"] == consumer_group
    assert result["consumer_name"] == "hes-worker:runtime-handoff-worker"
    assert result["job_run_id"] == job_run_id
    assert result["lineage"]["dispatch_request_identity"] == (
        f"{job_run_id}:retry_dispatch_request"
    )
    assert result["lineage"]["queue_message_id"] == claim_result["message"]["message_id"]
    assert result["lineage"]["claim_token"] == claim_result["claim"]["claim_token"]
    assert result["lineage"]["source_identifiers"]["job_run_id"] == job_run_id
    assert result["lineage"]["source_identifiers"]["command_id"] is not None
    assert result["lineage"]["source_identifiers"]["attempt_id"] is not None
    assert result["lineage"]["correlation_lineage"]["derived_correlation_id"] is not None
    assert payload["job_run"]["status"] == "running"
    assert payload["created_or_existing_attempt"]["status"] == "started"
    assert payload["related_command"]["id"] == result["related_command_id"]
    assert payload["created_or_existing_attempt"]["id"] == result["command_attempt_id"]

    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(result["command_attempt_id"]))
    command = db_session.get(MeterCommand, uuid.UUID(result["related_command_id"]))
    assert job_run is not None
    assert attempt is not None
    assert command is not None
    assert job_run.result_summary["runtime_execution_handoff"]["lineage"] == result["lineage"]
    assert (
        command.result_summary["runtime_execution_handoff"]["handoff_record_id"]
        == result["handoff_record_id"]
    )
    assert (
        attempt.execution_metadata["runtime_execution_handoff"]["handoff_record_id"]
        == result["handoff_record_id"]
    )
    assert attempt.execution_metadata["queue_runtime_handoff"]["message_id"] == (
        claim_result["message"]["message_id"]
    )
    assert attempt.execution_metadata["queue_runtime_handoff"]["dispatch_request_identity"] == (
        f"{job_run_id}:retry_dispatch_request"
    )

    redis_client.delete(stream_name)


def test_repeated_runtime_execution_handoff_returns_existing_durable_state(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, claim_result, stream_name, _, redis_client = _enqueue_and_claim_dispatch_message(
        client,
        db_session,
        monkeypatch,
    )

    first = client.post(
        "/api/v1/internal/queue/dispatch-messages/runtime-handoff",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "runtime-handoff-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )
    second = client.post(
        "/api/v1/internal/queue/dispatch-messages/runtime-handoff",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "runtime-handoff-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_result = first.json()["result"]
    second_result = second.json()["result"]
    assert second_result["handoff_record_id"] == first_result["handoff_record_id"]
    assert second_result["handed_off_at"] == first_result["handed_off_at"]
    assert second_result["command_attempt_id"] == first_result["command_attempt_id"]
    assert second.json()["created_or_existing_attempt"]["id"] == first.json()[
        "created_or_existing_attempt"
    ]["id"]
    command_attempt_count = db_session.scalar(
        select(func.count()).select_from(CommandExecutionAttempt).where(
            CommandExecutionAttempt.job_run_id == uuid.UUID(job_run_id)
        )
    )
    assert command_attempt_count == 1

    redis_client.delete(stream_name)


def test_runtime_execution_handoff_fails_when_claim_is_no_longer_pending(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, claim_result, stream_name, _, redis_client = _enqueue_and_claim_dispatch_message(
        client,
        db_session,
        monkeypatch,
    )

    ack = client.post(
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "runtime-handoff-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )
    assert ack.status_code == 200

    handoff = client.post(
        "/api/v1/internal/queue/dispatch-messages/runtime-handoff",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "runtime-handoff-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert handoff.status_code == 409
    assert "valid pending state" in handoff.json()["detail"]

    redis_client.delete(stream_name)
