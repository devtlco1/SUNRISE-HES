from __future__ import annotations

from sqlalchemy.orm import Session

from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_on_demand_read_submission import _submit_on_demand_read_command
from tests.test_commands_profile_capture_attempt_bootstrap import (
    _create_submitted_profile_capture_command,
)
from tests.test_commands_profile_capture_execute_now import _execute_profile_capture_now
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_commands_relay_control_execute_now import _execute_relay_control_now
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record
from tests.test_worker_runtime_executor_foundation import _create_load_profile_channel


def _get_recent_commands(
    client,
    token: str,
    *,
    limit: int = 20,
    family: str | None = None,
):
    params = {"limit": limit}
    if family is not None:
        params["family"] = family
    return client.get(
        "/api/v1/commands/recent",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )


def test_recent_commands_read_model_returns_profile_capture_items(
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
        code="commands-recent-profile-capture",
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
        idempotency_key="commands-recent-profile-capture-1",
    )
    assert execute_now.status_code == 200

    response = _get_recent_commands(client, token, family="profile_capture")

    assert response.status_code == 200
    payload = response.json()
    assert payload["family_filter"] == "profile_capture"
    assert payload["total"] >= 1
    item = next(
        item
        for item in payload["items"]
        if item["command_id"] == execute_now.json()["result"]["command_id"]
    )
    assert item["command_family"] == "profile_capture"
    assert item["command_category"] == "profile_capture"
    assert item["command_status"] == "succeeded"
    assert (
        item["runtime_execution_record_id"]
        == execute_now.json()["result"]["runtime_profile_read_execution_record_id"]
    )
    assert item["family_specific_outcome_summary"]["terminal_status_category"] == "acknowledged"


def test_recent_commands_read_model_returns_relay_control_items(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="commands-recent-relay-control",
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
        idempotency_key="commands-recent-relay-control-1",
    )
    assert execute_now.status_code == 200

    response = _get_recent_commands(client, token, family="relay_control")

    assert response.status_code == 200
    payload = response.json()
    assert payload["family_filter"] == "relay_control"
    assert payload["total"] >= 1
    item = next(
        item
        for item in payload["items"]
        if item["command_id"] == execute_now.json()["result"]["command_id"]
    )
    assert item["command_family"] == "relay_control"
    assert item["command_category"] == "remote_disconnect"
    assert item["command_status"] == "succeeded"
    assert (
        item["runtime_execution_record_id"]
        == execute_now.json()["result"]["runtime_relay_control_execution_record_id"]
    )
    assert item["family_specific_outcome_summary"]["relay_control_operation"] == "disconnect"
    assert item["family_specific_outcome_summary"]["relay_control_execution_outcome"] == "succeeded"


def test_recent_commands_read_model_returns_mixed_family_projection(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    profile_template_id = _create_command_template_for_category(
        client,
        token,
        code="commands-recent-mixed-profile-capture",
        category="profile_capture",
    )
    relay_template_id = _create_command_template_for_category(
        client,
        token,
        code="commands-recent-mixed-relay-control",
        category="remote_disconnect",
    )
    profile_execute = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=profile_template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="commands-recent-mixed-profile-capture-1",
    )
    relay_execute = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=relay_template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="commands-recent-mixed-relay-control-1",
    )
    assert profile_execute.status_code == 200
    assert relay_execute.status_code == 200

    response = _get_recent_commands(client, token, limit=10)

    assert response.status_code == 200
    payload = response.json()
    ids = {item["command_id"] for item in payload["items"]}
    assert profile_execute.json()["result"]["command_id"] in ids
    assert relay_execute.json()["result"]["command_id"] in ids
    families = {item["command_family"] for item in payload["items"]}
    assert "profile_capture" in families
    assert "relay_control" in families


def test_recent_commands_read_model_returns_bounded_response_when_downstream_artifacts_absent(
    client,
    db_session: Session,
) -> None:
    command_id, meter_id, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="commands-recent-submitted-profile-capture",
        idempotency_key="commands-recent-submitted-profile-capture-1",
    )
    token = _login_as_super_admin(client, db_session)

    response = _get_recent_commands(client, token, family="profile_capture")

    assert response.status_code == 200
    payload = response.json()
    item = next(item for item in payload["items"] if item["command_id"] == command_id)
    assert item["command_family"] == "profile_capture"
    assert item["command_status"] == "pending"
    assert item["meter_id"] == meter_id
    assert item["latest_command_execution_attempt_id"] is None
    assert item["latest_command_execution_attempt_status"] is None
    assert item["runtime_execution_record_id"] is None
    assert item["family_specific_outcome_summary"]["terminal_status_category"] is None
    assert item["orchestration_artifact_present"] is False
    assert item["terminalization_artifact_present"] is False
    assert item["execute_now_artifact_present"] is False


def test_recent_commands_read_model_excludes_unsupported_on_demand_read_commands(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    on_demand_template_id = _create_command_template_for_category(
        client,
        token,
        code="commands-recent-on-demand-read",
        category="on_demand_read",
    )
    on_demand_response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=on_demand_template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="commands-recent-on-demand-read-1",
    )
    assert on_demand_response.status_code == 200

    response = _get_recent_commands(client, token, limit=20)

    assert response.status_code == 200
    ids = {item["command_id"] for item in response.json()["items"]}
    assert on_demand_response.json()["id"] not in ids
