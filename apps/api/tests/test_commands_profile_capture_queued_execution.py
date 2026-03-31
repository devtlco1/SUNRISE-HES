from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_on_demand_read_queued_execution import (
    _build_real_redis_client,
    _configure_real_redis_settings,
)
from tests.test_commands_profile_capture_attempt_bootstrap import (
    _create_submitted_profile_capture_command,
)


def _enqueue_profile_capture_execution(
    client,
    command_id: str,
    *,
    enqueue_identifier: str = "profile-capture-queue-enqueue-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/enqueue-profile-capture-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "enqueue_identifier": enqueue_identifier,
            "enqueue_reason": "profile-capture-queued-foundation",
        },
    )


def _consume_next_profile_capture_execution(
    client,
    *,
    worker_identifier: str = "profile-capture-queue-worker-1",
    ensure_consumer_group: bool = True,
):
    return client.post(
        "/api/v1/internal/commands/profile-capture/consume-next-queued-execution",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": worker_identifier,
            "ensure_consumer_group": ensure_consumer_group,
            "consume_reason": "profile-capture-queued-foundation",
        },
    )


def test_profile_capture_queue_enqueue_succeeds_from_valid_command_context(
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
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-queue-enqueue-success",
        idempotency_key="profile-capture-queue-enqueue-success-1",
    )

    response = _enqueue_profile_capture_execution(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["queue_status"] == "enqueued"
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["profile_read_operation"] == "capture_load_profile"
    assert payload["result"]["reused_existing_enqueue"] is False
    assert payload["result"]["stream_name"] == stream_name
    assert payload["result"]["intended_worker_path"] == "commands.profile_capture.queue_worker"
    assert payload["related_command"]["current_status"] == "queued"

    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert command is not None
    assert command.current_status == CommandStatus.QUEUED
    assert command.result_summary is not None
    artifact = command.result_summary["profile_capture_queue_enqueue"]
    assert artifact["message_id"] == payload["result"]["message_id"]
    assert artifact["queue_message"]["contract_family"] == "profile_capture_queued_execution"
    assert artifact["queue_message"]["profile_read_operation"] == "capture_load_profile"
    assert artifact["queue_message"]["channel_count"] == 1

    entries = redis_client.xrange(stream_name)
    assert len(entries) == 1
    message_id, fields = entries[0]
    assert message_id == payload["result"]["message_id"]
    assert fields["dispatch_category"] == "profile_capture_queued_execution"
    assert fields["intended_worker_path"] == "commands.profile_capture.queue_worker"

    redis_client.delete(stream_name)


def test_profile_capture_queue_enqueue_refuses_non_eligible_command_context(
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
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-queue-enqueue-refusal",
        idempotency_key="profile-capture-queue-enqueue-refusal-1",
    )
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _enqueue_profile_capture_execution(client, command_id)

    assert response.status_code == 409
    assert "not queue-eligible" in response.json()["detail"].lower()


def test_profile_capture_queue_enqueue_is_idempotent_and_persists_message_contract(
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
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-queue-enqueue-idempotent",
        idempotency_key="profile-capture-queue-enqueue-idempotent-1",
    )

    first = _enqueue_profile_capture_execution(
        client,
        command_id,
        enqueue_identifier="profile-capture-queue-enqueue-idempotent-ctx",
    )
    second = _enqueue_profile_capture_execution(
        client,
        command_id,
        enqueue_identifier="profile-capture-queue-enqueue-idempotent-ctx",
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


def test_profile_capture_queue_worker_consumes_bounded_message_successfully(
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
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-queue-worker-success",
        idempotency_key="profile-capture-queue-worker-success-1",
    )
    enqueue_response = _enqueue_profile_capture_execution(
        client,
        command_id,
        enqueue_identifier="profile-capture-queue-worker-success-ctx",
    )
    assert enqueue_response.status_code == 200

    consume_response = _consume_next_profile_capture_execution(client)

    assert consume_response.status_code == 200
    payload = consume_response.json()
    assert payload["result"]["consume_status"] == "consumed"
    assert payload["result"]["acked"] is True
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["profile_read_operation"] == "capture_load_profile"
    assert payload["result"]["terminal_status_category"] == "acknowledged"
    assert payload["result"]["runtime_profile_read_execution_record_id"] is not None
    assert payload["result"]["queue_lease"]["stream_name"] == stream_name
    assert payload["result"]["queue_message"]["contract_family"] == "profile_capture_queued_execution"
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
        attempt.execution_metadata["profile_capture_queue_consumption"]["ack_receipt_id"]
        is not None
    )
    assert (
        job_run.result_summary["profile_capture_queue_consumption"]["queue_message"]["enqueue_identifier"]
        == "profile-capture-queue-worker-success-ctx"
    )
    assert redis_client.xpending_range(
        stream_name,
        consumer_group,
        min="-",
        max="+",
        count=10,
    ) == []

    redis_client.delete(stream_name)
