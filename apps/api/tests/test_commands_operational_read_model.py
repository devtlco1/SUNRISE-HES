from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_on_demand_read_submission import _submit_on_demand_read_command
from tests.test_commands_profile_capture_attempt_bootstrap import (
    _create_submitted_profile_capture_command,
)
from tests.test_commands_profile_capture_execute_now import _execute_profile_capture_now
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_commands_relay_control_attempt_bootstrap import (
    _create_submitted_relay_control_command,
)
from tests.test_commands_relay_control_execute_now import _execute_relay_control_now
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record
from tests.test_worker_runtime_executor_foundation import _create_load_profile_channel


def _get_command_operational_detail(client, token: str, command_id: str):
    return client.get(
        f"/api/v1/commands/{command_id}/detail",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_command_operational_detail_returns_profile_capture_projection(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="commands-operational-detail-profile-capture",
        category="profile_capture",
    )

    execute_now = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="commands-operational-detail-profile-capture-1",
    )
    assert execute_now.status_code == 200

    command_id = execute_now.json()["result"]["command_id"]
    response = _get_command_operational_detail(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["command_id"] == command_id
    assert payload["command_family"] == "profile_capture"
    assert payload["command_category"] == "profile_capture"
    assert payload["command_status"] == "succeeded"
    assert payload["meter_id"] == meter_id
    assert (
        payload["latest_command_execution_attempt_id"]
        == execute_now.json()["result"]["command_execution_attempt_id"]
    )
    assert payload["latest_command_execution_attempt_status"] == "succeeded"
    assert (
        payload["runtime_execution_record_id"]
        == execute_now.json()["result"]["runtime_profile_read_execution_record_id"]
    )
    assert payload["family_specific_outcome_summary"]["terminal_status_category"] == "acknowledged"
    assert payload["orchestration_artifact_present"] is True
    assert payload["terminalization_artifact_present"] is True
    assert payload["execute_now_artifact_present"] is True


def test_command_operational_detail_returns_relay_control_projection(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="commands-operational-detail-relay-control",
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
        idempotency_key="commands-operational-detail-relay-control-1",
    )
    assert execute_now.status_code == 200

    command_id = execute_now.json()["result"]["command_id"]
    response = _get_command_operational_detail(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["command_id"] == command_id
    assert payload["command_family"] == "relay_control"
    assert payload["command_category"] == "remote_disconnect"
    assert payload["command_status"] == "succeeded"
    assert payload["meter_id"] == meter_id
    assert (
        payload["latest_command_execution_attempt_id"]
        == execute_now.json()["result"]["command_execution_attempt_id"]
    )
    assert payload["latest_command_execution_attempt_status"] == "succeeded"
    assert (
        payload["runtime_execution_record_id"]
        == execute_now.json()["result"]["runtime_relay_control_execution_record_id"]
    )
    assert payload["family_specific_outcome_summary"]["relay_control_operation"] == "disconnect"
    assert payload["family_specific_outcome_summary"]["relay_control_execution_outcome"] == "succeeded"
    assert payload["orchestration_artifact_present"] is True
    assert payload["terminalization_artifact_present"] is True
    assert payload["execute_now_artifact_present"] is True


def test_command_operational_detail_returns_bounded_response_when_downstream_artifacts_absent(
    client,
    db_session: Session,
) -> None:
    command_id, meter_id, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="commands-operational-detail-submitted",
        idempotency_key="commands-operational-detail-submitted-1",
    )
    token = _login_as_super_admin(client, db_session)

    response = _get_command_operational_detail(client, token, command_id)

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["command_id"] == command_id
    assert payload["command_family"] == "profile_capture"
    assert payload["command_status"] == "pending"
    assert payload["meter_id"] == meter_id
    assert payload["latest_command_execution_attempt_id"] is None
    assert payload["latest_command_execution_attempt_status"] is None
    assert payload["runtime_execution_record_id"] is None
    assert payload["family_specific_outcome_summary"]["terminal_status_category"] is None
    assert payload["orchestration_artifact_present"] is False
    assert payload["terminalization_artifact_present"] is False
    assert payload["execute_now_artifact_present"] is False


def test_command_operational_detail_refuses_unsupported_command_family(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="commands-operational-detail-on-demand-read",
        category="on_demand_read",
    )

    create_command = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="commands-operational-detail-on-demand-read-1",
    )
    assert create_command.status_code == 200

    response = _get_command_operational_detail(client, token, create_command.json()["id"])

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_command_operational_detail_returns_not_found_for_unknown_command(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = _get_command_operational_detail(client, token, str(uuid.uuid4()))

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
