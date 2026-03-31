from __future__ import annotations

import socket
import uuid
from urllib.parse import urlsplit, urlunsplit

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import (
    CommandExecutionAttemptStatus,
    CommandStatus,
)
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_on_demand_read_attempt_bootstrap import (
    _create_submitted_on_demand_read_command,
)


def _resolve_local_test_redis_url(redis_url: str) -> str:
    parsed = urlsplit(redis_url)
    hostname = parsed.hostname
    if hostname is None:
        return redis_url
    try:
        socket.getaddrinfo(hostname, parsed.port or 6379)
        return redis_url
    except OSError:
        if hostname != "redis":
            return redis_url
    netloc = parsed.netloc.replace(hostname, "localhost", 1)
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _build_real_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _configure_real_redis_settings(monkeypatch, *, stream_name: str, consumer_group: str) -> None:
    monkeypatch.setattr(settings, "redis_url", _resolve_local_test_redis_url(settings.redis_url))
    monkeypatch.setattr(settings, "redis_queue_stream_name", stream_name)
    monkeypatch.setattr(settings, "redis_queue_consumer_group_name", consumer_group)


def _enqueue_on_demand_read_execution(
    client,
    command_id: str,
    *,
    enqueue_identifier: str = "on-demand-read-queue-enqueue-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/enqueue-on-demand-read-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "enqueue_identifier": enqueue_identifier,
            "enqueue_reason": "on-demand-read-queued-foundation",
        },
    )


def _consume_next_on_demand_read_execution(
    client,
    *,
    worker_identifier: str = "on-demand-read-queue-worker-1",
    ensure_consumer_group: bool = True,
):
    return client.post(
        "/api/v1/internal/commands/on-demand-read/consume-next-queued-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": worker_identifier,
            "ensure_consumer_group": ensure_consumer_group,
            "consume_reason": "on-demand-read-queued-foundation",
        },
    )


def test_on_demand_read_queue_enqueue_succeeds_from_valid_command_context(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group = f"hes-worker-group:{uuid.uuid4()}"
    _configure_real_redis_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group=consumer_group,
    )
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-queue-enqueue-success",
        idempotency_key="on-demand-read-queue-enqueue-success-1",
    )

    response = _enqueue_on_demand_read_execution(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["queue_status"] == "enqueued"
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["result"]["reused_existing_enqueue"] is False
    assert payload["result"]["stream_name"] == stream_name
    assert payload["result"]["intended_worker_path"] == "commands.on_demand_read.queue_worker"
    assert payload["related_command"]["current_status"] == "queued"

    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert command is not None
    assert command.current_status == CommandStatus.QUEUED
    assert command.result_summary is not None
    artifact = command.result_summary["on_demand_read_queue_enqueue"]
    assert artifact["message_id"] == payload["result"]["message_id"]
    assert artifact["queue_message"]["contract_family"] == "on_demand_read_queued_execution"
    assert artifact["queue_message"]["on_demand_read_operation"] == "read_billing_snapshot"

    entries = redis_client.xrange(stream_name)
    assert len(entries) == 1
    message_id, fields = entries[0]
    assert message_id == payload["result"]["message_id"]
    assert fields["dispatch_category"] == "on_demand_read_queued_execution"
    assert fields["intended_worker_path"] == "commands.on_demand_read.queue_worker"

    redis_client.delete(stream_name)


def test_on_demand_read_queue_enqueue_refuses_non_eligible_command_context(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group = f"hes-worker-group:{uuid.uuid4()}"
    _configure_real_redis_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group=consumer_group,
    )
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-queue-enqueue-refusal",
        idempotency_key="on-demand-read-queue-enqueue-refusal-1",
    )
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _enqueue_on_demand_read_execution(client, command_id)

    assert response.status_code == 409
    assert "not queue-eligible" in response.json()["detail"].lower()


def test_on_demand_read_queue_enqueue_is_idempotent_and_persists_message_contract(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group = f"hes-worker-group:{uuid.uuid4()}"
    _configure_real_redis_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group=consumer_group,
    )
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-queue-enqueue-idempotent",
        idempotency_key="on-demand-read-queue-enqueue-idempotent-1",
    )

    first = _enqueue_on_demand_read_execution(
        client,
        command_id,
        enqueue_identifier="on-demand-read-queue-enqueue-idempotent-ctx",
    )
    second = _enqueue_on_demand_read_execution(
        client,
        command_id,
        enqueue_identifier="on-demand-read-queue-enqueue-idempotent-ctx",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["message_id"] == second.json()["result"]["message_id"]
    assert second.json()["result"]["reused_existing_enqueue"] is True
    assert len(redis_client.xrange(stream_name)) == 1
    assert (
        first.json()["result"]["queue_message"]["contract_version"]
        == second.json()["result"]["queue_message"]["contract_version"]
        == "v1"
    )

    redis_client.delete(stream_name)


def test_on_demand_read_queue_worker_consumes_bounded_message_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group = f"hes-worker-group:{uuid.uuid4()}"
    _configure_real_redis_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group=consumer_group,
    )
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-queue-worker-success",
        idempotency_key="on-demand-read-queue-worker-success-1",
    )
    enqueue_response = _enqueue_on_demand_read_execution(
        client,
        command_id,
        enqueue_identifier="on-demand-read-queue-worker-success-ctx",
    )
    assert enqueue_response.status_code == 200

    consume_response = _consume_next_on_demand_read_execution(client)

    assert consume_response.status_code == 200
    payload = consume_response.json()
    assert payload["result"]["consume_status"] == "consumed"
    assert payload["result"]["acked"] is True
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["result"]["on_demand_read_execution_outcome"] == "succeeded"
    assert payload["result"]["queue_lease"]["stream_name"] == stream_name
    assert payload["result"]["queue_message"]["contract_family"] == "on_demand_read_queued_execution"
    assert payload["related_command"]["current_status"] == "succeeded"
    assert payload["created_or_existing_attempt"]["status"] == "succeeded"
    assert payload["job_run"]["status"] == "succeeded"

    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    attempt = db_session.get(
        CommandExecutionAttempt,
        uuid.UUID(payload["result"]["command_execution_attempt_id"]),
    )
    assert command is not None
    assert attempt is not None
    job_run = db_session.get(JobRun, attempt.job_run_id)
    assert job_run is not None
    assert command.current_status == CommandStatus.SUCCEEDED
    assert attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert job_run.status == JobRunStatus.SUCCEEDED
    assert (
        attempt.execution_metadata["on_demand_read_queue_consumption"]["ack_receipt_id"]
        is not None
    )
    assert (
        job_run.result_summary["on_demand_read_queue_consumption"]["queue_message"]["enqueue_identifier"]
        == "on-demand-read-queue-worker-success-ctx"
    )
    assert redis_client.xpending_range(
        stream_name,
        consumer_group,
        min="-",
        max="+",
        count=10,
    ) == []

    redis_client.delete(stream_name)
