from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_on_demand_read_submission import _submit_on_demand_read_command
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_commands_on_demand_read_queued_execution import (
    _build_real_redis_client,
    _configure_real_redis_settings,
)
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _execute_on_demand_read_now_queued(
    client,
    token: str,
    meter_id: str,
    *,
    command_template_id: str,
    endpoint_assignment_id: str,
    protocol_association_profile_id: str,
    on_demand_read_operation: str = "read_billing_snapshot",
    idempotency_key: str | None = None,
):
    return client.post(
        f"/api/v1/meters/{meter_id}/commands/on-demand-read/execute-now-queued",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": command_template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_association_profile_id,
            "on_demand_read_operation": on_demand_read_operation,
            "priority": "high",
            "idempotency_key": idempotency_key,
            "notes": "On-demand-read queued execute now request",
            "queued_execute_now_reason": "on-demand-read-queued-execute-now",
        },
    )


def test_on_demand_read_queued_execute_now_succeeds_from_valid_application_request(
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
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-queued-execute-now-success",
        category="on_demand_read",
    )

    response = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-execute-now-success-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["queued_execute_now_status"] == "queued"
    assert payload["result"]["command_status"] == "queued"
    assert payload["result"]["queue_enqueue_status"] == "enqueued"
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["result"]["reused_existing_queued_execute_now"] is False
    assert payload["result"]["reused_existing_enqueue"] is False
    assert payload["result"]["command_execution_attempt_id"] is None
    assert payload["related_command"]["current_status"] == "queued"
    assert payload["created_or_existing_attempt"] is None

    command = db_session.get(MeterCommand, uuid.UUID(payload["result"]["command_id"]))
    assert command is not None
    assert command.current_status == CommandStatus.QUEUED
    assert command.result_summary is not None
    assert "on_demand_read_queue_enqueue" in command.result_summary
    assert "on_demand_read_queued_execute_now" in command.result_summary
    latest_attempt = db_session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command.id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )
    assert latest_attempt is None
    assert len(redis_client.xrange(stream_name)) == 1

    redis_client.delete(stream_name)


def test_on_demand_read_queued_execute_now_is_idempotent_for_same_request_context(
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
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-queued-execute-now-repeat",
        category="on_demand_read",
    )

    first = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-execute-now-repeat-1",
    )
    second = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-execute-now-repeat-1",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["command_id"] == second.json()["result"]["command_id"]
    assert first.json()["result"]["queue_message_id"] == second.json()["result"]["queue_message_id"]
    assert second.json()["result"]["reused_existing_queued_execute_now"] is True
    assert second.json()["result"]["reused_existing_enqueue"] is True
    assert len(redis_client.xrange(stream_name)) == 1

    redis_client.delete(stream_name)


def test_on_demand_read_queued_execute_now_refuses_when_submission_prerequisites_are_invalid(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-queued-execute-now-wrong-template",
        category="profile_capture",
    )

    response = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-execute-now-wrong-template-1",
    )

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_on_demand_read_queued_execute_now_refuses_when_reused_command_is_not_queue_eligible(
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
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-queued-execute-now-ineligible",
        category="on_demand_read",
    )
    submit_response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-execute-now-ineligible-1",
    )
    assert submit_response.status_code == 200
    command_id = submit_response.json()["id"]
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=str(command.command_template_id),
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-execute-now-ineligible-1",
    )

    assert response.status_code == 409
    assert "not queue-eligible" in response.json()["detail"].lower()


def test_on_demand_read_queued_execute_now_persists_compact_durable_linkage_artifact(
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
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-queued-execute-now-artifact",
        category="on_demand_read",
    )

    response = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-execute-now-artifact-1",
    )

    assert response.status_code == 200
    payload = response.json()
    command = db_session.get(MeterCommand, uuid.UUID(payload["result"]["command_id"]))
    assert command is not None
    queued_execute_now = command.result_summary["on_demand_read_queued_execute_now"]
    queue_enqueue = command.result_summary["on_demand_read_queue_enqueue"]
    assert queued_execute_now["command_id"] == payload["result"]["command_id"]
    assert queued_execute_now["command_execution_attempt_id"] is None
    assert queued_execute_now["queue_enqueue_status"] == payload["result"]["queue_enqueue_status"]
    assert queued_execute_now["queue_message_id"] == payload["result"]["queue_message_id"]
    assert queued_execute_now["on_demand_read_operation"] == payload["result"]["on_demand_read_operation"]
    assert queued_execute_now["snapshot_type"] == payload["result"]["snapshot_type"]
    assert queue_enqueue["message_id"] == queued_execute_now["queue_message_id"]
    assert queue_enqueue["enqueue_identifier"] == queued_execute_now["queued_execute_now_identifier"]

    redis_client.delete(stream_name)
