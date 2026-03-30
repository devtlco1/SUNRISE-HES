from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_commands_relay_control_submission import _submit_relay_control_command
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _bootstrap_relay_control_attempt(client, command_id: str, *, bootstrap_identifier: str = "bootstrap-relay-1"):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/bootstrap-relay-control-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "bootstrap_identifier": bootstrap_identifier,
            "bootstrap_reason": "relay-control-bootstrap",
        },
    )


def _create_submitted_relay_control_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    category: str,
    relay_operation: str,
    idempotency_key: str,
) -> tuple[str, str, str, str]:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code=command_template_code,
        category=category,
    )
    response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation=relay_operation,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 200
    return response.json()["id"], endpoint_assignment_id, protocol_profile_id, relay_operation


def test_bootstrap_relay_control_attempt_creates_attempt_from_valid_command(
    client,
    db_session: Session,
) -> None:
    command_id, endpoint_assignment_id, protocol_profile_id, relay_operation = (
        _create_submitted_relay_control_command(
            client,
            db_session,
            command_template_code="relay-control-bootstrap-valid",
            category="remote_disconnect",
            relay_operation="disconnect",
            idempotency_key="relay-control-bootstrap-valid-1",
        )
    )

    response = _bootstrap_relay_control_attempt(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["bootstrap_status"] == "bootstrapped"
    assert payload["result"]["reused_existing_attempt"] is False
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["endpoint_assignment_id"] == endpoint_assignment_id
    assert payload["result"]["protocol_association_profile_id"] == protocol_profile_id
    assert payload["result"]["relay_control_operation"] == relay_operation
    assert payload["related_command"]["current_status"] == "in_progress"
    assert payload["created_or_existing_attempt"]["status"] == "started"
    assert (
        payload["created_or_existing_attempt"]["request_snapshot"]["relay_control_operation"]
        == relay_operation
    )
    assert (
        payload["created_or_existing_attempt"]["execution_metadata"]["relay_control_attempt_bootstrap"][
            "bootstrap_identifier"
        ]
        == "bootstrap-relay-1"
    )


def test_bootstrap_relay_control_attempt_refuses_non_eligible_command_status(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-bootstrap-terminal",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-bootstrap-terminal-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_relay_control_attempt(client, command_id)

    assert response.status_code == 409
    assert "not bootstrap-eligible" in response.json()["detail"].lower()


def test_bootstrap_relay_control_attempt_refuses_missing_normalized_payload(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-bootstrap-missing-normalized",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-bootstrap-missing-normalized-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.normalized_payload = None
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_relay_control_attempt(client, command_id)

    assert response.status_code == 409
    assert "missing normalized payload" in response.json()["detail"].lower()


def test_bootstrap_relay_control_attempt_refuses_endpoint_continuity_mismatch(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-bootstrap-endpoint-mismatch",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-bootstrap-endpoint-mismatch-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.endpoint_assignment_id = None
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_relay_control_attempt(client, command_id)

    assert response.status_code == 409
    assert "endpoint continuity" in response.json()["detail"].lower()


def test_bootstrap_relay_control_attempt_refuses_protocol_continuity_mismatch(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-bootstrap-protocol-mismatch",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-bootstrap-protocol-mismatch-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.protocol_association_profile_id = None
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_relay_control_attempt(client, command_id)

    assert response.status_code == 409
    assert "protocol continuity" in response.json()["detail"].lower()


def test_bootstrap_relay_control_attempt_refuses_inconsistent_relay_target_linkage(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-bootstrap-target-linkage",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-bootstrap-target-linkage-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    normalized_payload = dict(command.normalized_payload or {})
    relay_control = dict(normalized_payload["relay_control"])
    target_object = dict(relay_control["target_object"])
    target_object["obis_code"] = "1.0.99.1.0.255"
    relay_control["target_object"] = target_object
    normalized_payload["relay_control"] = relay_control
    command.normalized_payload = normalized_payload
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_relay_control_attempt(client, command_id)

    assert response.status_code == 409
    assert "target linkage" in response.json()["detail"].lower()


def test_bootstrap_relay_control_attempt_reuses_existing_attempt_idempotently(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-bootstrap-reuse",
        category="remote_reconnect",
        relay_operation="reconnect",
        idempotency_key="relay-control-bootstrap-reuse-1",
    )

    first = _bootstrap_relay_control_attempt(client, command_id)
    second = _bootstrap_relay_control_attempt(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert second.json()["result"]["reused_existing_attempt"] is True


def test_bootstrap_relay_control_attempt_persists_durable_bootstrap_artifact(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, relay_operation = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-bootstrap-artifact",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-bootstrap-artifact-1",
    )

    response = _bootstrap_relay_control_attempt(client, command_id, bootstrap_identifier="bootstrap-relay-artifact-1")

    assert response.status_code == 200
    attempt_id = UUID(response.json()["result"]["command_execution_attempt_id"])
    command = db_session.get(MeterCommand, UUID(command_id))
    attempt = db_session.scalar(
        select(CommandExecutionAttempt).where(CommandExecutionAttempt.id == attempt_id)
    )
    assert command is not None
    assert attempt is not None
    assert attempt.status == CommandExecutionAttemptStatus.STARTED
    assert attempt.request_snapshot == command.normalized_payload
    assert attempt.execution_metadata["relay_control_attempt_bootstrap"]["command_id"] == command_id
    assert (
        attempt.execution_metadata["relay_control_attempt_bootstrap"]["relay_control_operation"]
        == relay_operation
    )
    assert (
        command.result_summary["relay_control_attempt_bootstrap"]["command_execution_attempt_id"]
        == str(attempt.id)
    )
