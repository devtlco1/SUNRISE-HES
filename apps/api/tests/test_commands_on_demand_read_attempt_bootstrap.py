from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_on_demand_read_submission import _submit_on_demand_read_command
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _bootstrap_on_demand_read_attempt(
    client,
    command_id: str,
    *,
    bootstrap_identifier: str = "bootstrap-on-demand-read-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/bootstrap-on-demand-read-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "bootstrap_identifier": bootstrap_identifier,
            "bootstrap_reason": "on-demand-read-bootstrap",
        },
    )


def _create_submitted_on_demand_read_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    idempotency_key: str,
) -> tuple[str, str, str, str]:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code=command_template_code,
        category="on_demand_read",
    )
    response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 200
    return response.json()["id"], meter_id, endpoint_assignment_id, protocol_profile_id


def test_bootstrap_on_demand_read_attempt_creates_attempt_from_valid_command(
    client,
    db_session: Session,
) -> None:
    command_id, _, endpoint_assignment_id, protocol_profile_id = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-valid",
        idempotency_key="on-demand-read-bootstrap-valid-1",
    )

    response = _bootstrap_on_demand_read_attempt(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["bootstrap_status"] == "bootstrapped"
    assert payload["result"]["reused_existing_attempt"] is False
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["endpoint_assignment_id"] == endpoint_assignment_id
    assert payload["result"]["protocol_association_profile_id"] == protocol_profile_id
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["related_command"]["current_status"] == "in_progress"
    assert payload["created_or_existing_attempt"]["status"] == "started"
    assert (
        payload["created_or_existing_attempt"]["request_snapshot"]["on_demand_read_operation"]
        == "read_billing_snapshot"
    )
    assert (
        payload["created_or_existing_attempt"]["execution_metadata"]["on_demand_read_attempt_bootstrap"][
            "bootstrap_identifier"
        ]
        == "bootstrap-on-demand-read-1"
    )


def test_bootstrap_on_demand_read_attempt_refuses_non_eligible_command_status(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-terminal",
        idempotency_key="on-demand-read-bootstrap-terminal-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_on_demand_read_attempt(client, command_id)

    assert response.status_code == 409
    assert "not bootstrap-eligible" in response.json()["detail"].lower()


def test_bootstrap_on_demand_read_attempt_refuses_missing_or_invalid_normalized_payload(
    client,
    db_session: Session,
) -> None:
    missing_command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-missing-normalized",
        idempotency_key="on-demand-read-bootstrap-missing-normalized-1",
    )
    missing_command = db_session.get(MeterCommand, UUID(missing_command_id))
    assert missing_command is not None
    missing_command.normalized_payload = None
    db_session.add(missing_command)
    db_session.commit()

    missing_response = _bootstrap_on_demand_read_attempt(client, missing_command_id)

    invalid_command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-invalid-linkage",
        idempotency_key="on-demand-read-bootstrap-invalid-linkage-1",
    )
    invalid_command = db_session.get(MeterCommand, UUID(invalid_command_id))
    assert invalid_command is not None
    invalid_payload = dict(invalid_command.normalized_payload or {})
    invalid_payload["on_demand_read"] = {
        **dict(invalid_payload.get("on_demand_read") or {}),
        "snapshot_type": "instantaneous",
    }
    invalid_command.normalized_payload = invalid_payload
    db_session.add(invalid_command)
    db_session.commit()

    invalid_response = _bootstrap_on_demand_read_attempt(client, invalid_command_id)

    assert missing_response.status_code == 409
    assert "missing normalized payload" in missing_response.json()["detail"].lower()
    assert invalid_response.status_code == 409
    assert "billing-snapshot linkage" in invalid_response.json()["detail"].lower()


def test_bootstrap_on_demand_read_attempt_refuses_endpoint_or_protocol_continuity_mismatch(
    client,
    db_session: Session,
) -> None:
    endpoint_command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-endpoint-mismatch",
        idempotency_key="on-demand-read-bootstrap-endpoint-mismatch-1",
    )
    endpoint_command = db_session.get(MeterCommand, UUID(endpoint_command_id))
    assert endpoint_command is not None
    endpoint_command.endpoint_assignment_id = None
    db_session.add(endpoint_command)
    db_session.commit()

    endpoint_response = _bootstrap_on_demand_read_attempt(client, endpoint_command_id)

    protocol_command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-protocol-mismatch",
        idempotency_key="on-demand-read-bootstrap-protocol-mismatch-1",
    )
    protocol_command = db_session.get(MeterCommand, UUID(protocol_command_id))
    assert protocol_command is not None
    protocol_command.protocol_association_profile_id = None
    db_session.add(protocol_command)
    db_session.commit()

    protocol_response = _bootstrap_on_demand_read_attempt(client, protocol_command_id)

    assert endpoint_response.status_code == 409
    assert "endpoint continuity" in endpoint_response.json()["detail"].lower()
    assert protocol_response.status_code == 409
    assert "protocol continuity" in protocol_response.json()["detail"].lower()


def test_bootstrap_on_demand_read_attempt_reuses_existing_attempt_idempotently(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-reuse",
        idempotency_key="on-demand-read-bootstrap-reuse-1",
    )

    first = _bootstrap_on_demand_read_attempt(client, command_id)
    second = _bootstrap_on_demand_read_attempt(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert second.json()["result"]["reused_existing_attempt"] is True


def test_bootstrap_on_demand_read_attempt_persists_durable_bootstrap_artifact(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-bootstrap-artifact",
        idempotency_key="on-demand-read-bootstrap-artifact-1",
    )

    response = _bootstrap_on_demand_read_attempt(
        client,
        command_id,
        bootstrap_identifier="bootstrap-on-demand-artifact-1",
    )

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
    assert (
        attempt.execution_metadata["on_demand_read_attempt_bootstrap"]["command_id"] == command_id
    )
    assert (
        attempt.execution_metadata["on_demand_read_attempt_bootstrap"]["on_demand_read_operation"]
        == "read_billing_snapshot"
    )
    assert (
        command.result_summary["on_demand_read_attempt_bootstrap"]["command_execution_attempt_id"]
        == str(attempt.id)
    )
