from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_on_demand_read_attempt_bootstrap import (
    _create_submitted_on_demand_read_command,
)
from tests.test_commands_on_demand_read_queued_execute_now import (
    _execute_on_demand_read_now_queued,
)
from tests.test_commands_on_demand_read_queued_execution import (
    _build_real_redis_client,
    _configure_real_redis_settings,
    _consume_next_on_demand_read_execution,
)
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _get_on_demand_read_queued_status(client, token: str, command_id: str):
    return client.get(
        f"/api/v1/commands/{command_id}/on-demand-read-queued-status",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_on_demand_read_queued_status_returns_compact_queued_execute_now_lineage(
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
        code="on-demand-read-queued-status-readback-queued",
        category="on_demand_read",
    )
    queued_execute_now = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-status-readback-queued-1",
    )
    assert queued_execute_now.status_code == 200
    command_id = queued_execute_now.json()["result"]["command_id"]

    response = _get_on_demand_read_queued_status(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["command_status"] == "queued"
    assert payload["result"]["queue_enqueue_status"] == "enqueued"
    assert payload["result"]["queue_message_id"] == queued_execute_now.json()["result"]["queue_message_id"]
    assert payload["result"]["queue_consumption_status"] is None
    assert payload["result"]["command_execution_attempt_id"] is None
    assert payload["result"]["runtime_on_demand_read_execution_record_id"] is None
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["result"]["worker_consumed"] is False
    assert payload["result"]["queued_execute_now_artifact_present"] is True
    assert payload["result"]["queue_enqueue_artifact_present"] is True
    assert payload["result"]["queue_consumption_artifact_present"] is False
    assert payload["result"]["orchestration_artifact_present"] is False
    assert payload["result"]["terminalization_artifact_present"] is False
    assert payload["result"]["final_execution_outcome"] is None
    assert payload["result"]["reused_existing_queued_execute_now"] is False
    assert payload["result"]["reused_existing_enqueue"] is False

    redis_client.delete(stream_name)


def test_on_demand_read_queued_status_returns_consumed_runtime_lineage_when_worker_has_run(
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
        code="on-demand-read-queued-status-readback-consumed",
        category="on_demand_read",
    )
    queued_execute_now = _execute_on_demand_read_now_queued(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-queued-status-readback-consumed-1",
    )
    assert queued_execute_now.status_code == 200
    command_id = queued_execute_now.json()["result"]["command_id"]
    consume = _consume_next_on_demand_read_execution(client)
    assert consume.status_code == 200

    response = _get_on_demand_read_queued_status(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["command_status"] == "succeeded"
    assert payload["result"]["queue_enqueue_status"] == "enqueued"
    assert payload["result"]["queue_message_id"] == queued_execute_now.json()["result"]["queue_message_id"]
    assert payload["result"]["queue_consumption_status"] == "consumed"
    assert payload["result"]["command_execution_attempt_id"] is not None
    assert payload["result"]["runtime_on_demand_read_execution_record_id"] is not None
    assert payload["result"]["worker_consumed"] is True
    assert payload["result"]["queue_consumption_artifact_present"] is True
    assert payload["result"]["orchestration_artifact_present"] is True
    assert payload["result"]["terminalization_artifact_present"] is True
    assert payload["result"]["final_execution_outcome"] == "succeeded"

    redis_client.delete(stream_name)


def test_on_demand_read_queued_status_returns_bounded_response_when_queued_artifacts_are_absent(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-queued-status-readback-submitted",
        idempotency_key="on-demand-read-queued-status-readback-submitted-1",
    )
    token = _login_as_super_admin(client, db_session)

    response = _get_on_demand_read_queued_status(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["command_status"] == "pending"
    assert payload["result"]["queue_enqueue_status"] is None
    assert payload["result"]["queue_message_id"] is None
    assert payload["result"]["queue_consumption_status"] is None
    assert payload["result"]["runtime_on_demand_read_execution_record_id"] is None
    assert payload["result"]["worker_consumed"] is False
    assert payload["result"]["queued_execute_now_artifact_present"] is False
    assert payload["result"]["queue_enqueue_artifact_present"] is False
    assert payload["result"]["queue_consumption_artifact_present"] is False
    assert payload["result"]["orchestration_artifact_present"] is False
    assert payload["result"]["terminalization_artifact_present"] is False
    assert payload["result"]["final_execution_outcome"] is None


def test_on_demand_read_queued_status_refuses_non_on_demand_read_command(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(
        db_session, meter_id
    )
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-queued-status-readback-wrong-category",
        category="profile_capture",
    )
    create_command = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "priority": "normal",
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_profile_id,
            "request_payload": {"operation": "capture-profile"},
            "normalized_payload": {"operation": "capture-profile"},
            "idempotency_key": "on-demand-read-queued-status-readback-wrong-category-1",
        },
    )
    assert create_command.status_code == 201

    response = _get_on_demand_read_queued_status(client, token, create_command.json()["id"])

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_on_demand_read_queued_status_returns_not_found_for_unknown_command(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = _get_on_demand_read_queued_status(client, token, str(uuid.uuid4()))

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
