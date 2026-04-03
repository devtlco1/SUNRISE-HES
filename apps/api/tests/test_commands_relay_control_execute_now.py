from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_commands_relay_control_submission import _submit_relay_control_command
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _execute_relay_control_now(
    client,
    token: str,
    meter_id: str,
    *,
    command_template_id: str | None = None,
    relay_operation: str,
    endpoint_assignment_id: str,
    protocol_association_profile_id: str,
    idempotency_key: str | None = None,
):
    json = {
        "relay_operation": relay_operation,
        "endpoint_assignment_id": endpoint_assignment_id,
        "protocol_association_profile_id": protocol_association_profile_id,
        "priority": "high",
        "idempotency_key": idempotency_key,
        "notes": "Relay control execute now request",
        "execute_now_reason": "relay-control-execute-now",
    }
    if command_template_id is not None:
        json["command_template_id"] = command_template_id
    return client.post(
        f"/api/v1/meters/{meter_id}/commands/relay-control/execute-now",
        headers={"Authorization": f"Bearer {token}"},
        json=json,
    )


def test_relay_control_execute_now_succeeds_from_valid_application_request(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-execute-now-success",
        category="remote_disconnect",
    )

    response = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-success-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["execute_now_status"] == "executed"
    assert payload["result"]["command_status"] == "succeeded"
    assert payload["result"]["relay_control_operation"] == "disconnect"
    assert payload["result"]["relay_control_execution_outcome"] == "succeeded"
    assert payload["result"]["orchestration_artifact_present"] is True
    assert payload["result"]["terminalization_artifact_present"] is True
    assert payload["result"]["reused_existing_execute_now"] is False

    command = db_session.get(MeterCommand, UUID(payload["result"]["command_id"]))
    attempt = db_session.get(
        CommandExecutionAttempt,
        UUID(payload["result"]["command_execution_attempt_id"]),
    )
    assert command is not None
    assert attempt is not None
    assert command.current_status == CommandStatus.SUCCEEDED
    assert attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert (
        attempt.execution_metadata["relay_control_execute_now"][
            "runtime_relay_control_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_relay_control_execution"][
            "relay_control_execution_record_id"
        ]
    )


def test_relay_control_execute_now_uses_default_template_when_not_supplied(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)

    response = _execute_relay_control_now(
        client,
        token,
        meter_id,
        relay_operation="reconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-default-template-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["related_command"]["command_template_code"] == "default-relay-control-reconnect"
    assert payload["related_command"]["command_template_name"] == "Default Relay Reconnect"
    assert payload["result"]["relay_control_operation"] == "reconnect"
    assert payload["result"]["relay_control_execution_outcome"] == "succeeded"


def test_relay_control_execute_now_is_idempotent_for_same_request_context(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-execute-now-repeat",
        category="remote_reconnect",
    )

    first = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="reconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-repeat-1",
    )
    second = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="reconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-repeat-1",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["command_id"] == second.json()["result"]["command_id"]
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert (
        first.json()["result"]["runtime_relay_control_execution_record_id"]
        == second.json()["result"]["runtime_relay_control_execution_record_id"]
    )
    assert second.json()["result"]["reused_existing_execute_now"] is True


def test_relay_control_execute_now_refuses_when_submission_prerequisites_are_invalid(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-execute-now-wrong-template",
        category="profile_capture",
    )

    response = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-wrong-template-1",
    )

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_relay_control_execute_now_refuses_when_reused_command_is_not_execution_eligible(
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
        code="relay-control-execute-now-ineligible",
        category="remote_disconnect",
    )
    submit_response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-ineligible-1",
    )
    assert submit_response.status_code == 200
    command_id = submit_response.json()["id"]
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=str(command.command_template_id),
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-ineligible-1",
    )

    assert response.status_code == 409
    assert "not execution-eligible" in response.json()["detail"].lower()


def test_relay_control_execute_now_persists_compact_durable_linkage_artifact(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-execute-now-artifact",
        category="remote_disconnect",
    )

    response = _execute_relay_control_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-execute-now-artifact-1",
    )

    assert response.status_code == 200
    payload = response.json()
    attempt = db_session.get(
        CommandExecutionAttempt,
        UUID(payload["result"]["command_execution_attempt_id"]),
    )
    command = db_session.get(MeterCommand, UUID(payload["result"]["command_id"]))
    assert attempt is not None
    assert command is not None
    job_run = db_session.get(JobRun, attempt.job_run_id)
    assert job_run is not None
    artifact = attempt.execution_metadata["relay_control_execute_now"]
    assert artifact["command_id"] == payload["result"]["command_id"]
    assert artifact["command_execution_attempt_id"] == payload["result"]["command_execution_attempt_id"]
    assert (
        artifact["runtime_relay_control_execution_record_id"]
        == payload["result"]["runtime_relay_control_execution_record_id"]
    )
    assert artifact["relay_control_operation"] == payload["result"]["relay_control_operation"]
    assert (
        artifact["relay_control_execution_outcome"]
        == payload["result"]["relay_control_execution_outcome"]
    )
    assert artifact["orchestration_artifact_present"] is True
    assert artifact["terminalization_artifact_present"] is True
    assert (
        command.result_summary["relay_control_execute_now"]["execute_now_identifier"]
        == artifact["execute_now_identifier"]
    )
    assert (
        job_run.result_summary["relay_control_execute_now"][
            "runtime_relay_control_execution_record_id"
        ]
        == artifact["runtime_relay_control_execution_record_id"]
    )
    assert job_run.status == JobRunStatus.SUCCEEDED
