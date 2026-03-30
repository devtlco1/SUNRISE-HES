from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_commands_relay_control_attempt_bootstrap import (
    _create_submitted_relay_control_command,
)
from tests.test_commands_relay_control_execute_now import _execute_relay_control_now
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _get_relay_control_status(client, token: str, command_id: str):
    return client.get(
        f"/api/v1/commands/{command_id}/relay-control-status",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_relay_control_status_readback_returns_compact_completed_execute_now_lineage(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-status-readback-success",
        category="remote_disconnect",
    )

    execute_now = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-status-readback-success-1",
    )
    assert execute_now.status_code == 200
    command_id = execute_now.json()["result"]["command_id"]

    response = _get_relay_control_status(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["command_status"] == "succeeded"
    assert payload["result"]["relay_control_operation"] == "disconnect"
    assert (
        payload["result"]["command_execution_attempt_id"]
        == execute_now.json()["result"]["command_execution_attempt_id"]
    )
    assert (
        payload["result"]["runtime_relay_control_execution_record_id"]
        == execute_now.json()["result"]["runtime_relay_control_execution_record_id"]
    )
    assert payload["result"]["relay_control_execution_outcome"] == "succeeded"
    assert payload["result"]["orchestration_artifact_present"] is True
    assert payload["result"]["terminalization_artifact_present"] is True
    assert payload["result"]["execute_now_artifact_present"] is True
    assert payload["result"]["reused_existing_execute_now"] is False
    assert payload["result"]["reused_existing_orchestration"] is False
    assert payload["result"]["reused_existing_terminalization"] is False


def test_relay_control_status_readback_returns_bounded_response_when_downstream_artifacts_are_absent(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-status-readback-submitted",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-status-readback-submitted-1",
    )
    token = _login_as_super_admin(client, db_session)

    response = _get_relay_control_status(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["command_status"] == "pending"
    assert payload["result"]["relay_control_operation"] == "disconnect"
    assert payload["result"]["command_execution_attempt_id"] is None
    assert payload["result"]["runtime_relay_control_execution_record_id"] is None
    assert payload["result"]["relay_control_execution_outcome"] is None
    assert payload["result"]["orchestration_artifact_present"] is False
    assert payload["result"]["terminalization_artifact_present"] is False
    assert payload["result"]["execute_now_artifact_present"] is False


def test_relay_control_status_readback_refuses_non_relay_control_command(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-status-readback-wrong-category",
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
            "idempotency_key": "relay-control-status-readback-wrong-category-1",
        },
    )
    assert create_command.status_code == 201

    response = _get_relay_control_status(client, token, create_command.json()["id"])

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_relay_control_status_readback_returns_not_found_for_unknown_command(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = _get_relay_control_status(client, token, str(uuid.uuid4()))

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
