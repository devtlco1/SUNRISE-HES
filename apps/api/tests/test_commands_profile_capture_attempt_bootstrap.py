from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_submission import (
    _create_command_template_for_category,
    _submit_profile_capture_command,
)
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record
from tests.test_worker_runtime_executor_foundation import _create_load_profile_channel


def _bootstrap_profile_capture_attempt(client, command_id: str, *, bootstrap_identifier: str = "bootstrap-profile-1"):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/bootstrap-profile-capture-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "bootstrap_identifier": bootstrap_identifier,
            "bootstrap_reason": "profile-capture-bootstrap",
        },
    )


def _create_submitted_profile_capture_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    idempotency_key: str,
) -> tuple[str, str, str, str, str]:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code=command_template_code,
        category="profile_capture",
    )
    response = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 200
    return response.json()["id"], meter_id, endpoint_assignment_id, protocol_profile_id, channel_id


def test_bootstrap_profile_capture_attempt_creates_attempt_from_valid_command(
    client,
    db_session: Session,
) -> None:
    command_id, _, endpoint_assignment_id, protocol_profile_id, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-bootstrap-valid",
        idempotency_key="profile-capture-bootstrap-valid-1",
    )

    response = _bootstrap_profile_capture_attempt(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["bootstrap_status"] == "bootstrapped"
    assert payload["result"]["reused_existing_attempt"] is False
    assert payload["result"]["command_id"] == command_id
    assert payload["result"]["endpoint_assignment_id"] == endpoint_assignment_id
    assert payload["result"]["protocol_association_profile_id"] == protocol_profile_id
    assert payload["related_command"]["current_status"] == "in_progress"
    assert payload["created_or_existing_attempt"]["status"] == "started"
    assert payload["created_or_existing_attempt"]["request_snapshot"]["profile_read_operation"] == "capture_load_profile"
    assert payload["created_or_existing_attempt"]["execution_metadata"]["profile_capture_attempt_bootstrap"]["bootstrap_identifier"] == "bootstrap-profile-1"


def test_bootstrap_profile_capture_attempt_refuses_non_eligible_command_status(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-bootstrap-terminal",
        idempotency_key="profile-capture-bootstrap-terminal-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_profile_capture_attempt(client, command_id)

    assert response.status_code == 409
    assert "not bootstrap-eligible" in response.json()["detail"].lower()


def test_bootstrap_profile_capture_attempt_refuses_missing_normalized_payload(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-bootstrap-missing-normalized",
        idempotency_key="profile-capture-bootstrap-missing-normalized-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.normalized_payload = None
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_profile_capture_attempt(client, command_id)

    assert response.status_code == 409
    assert "missing normalized payload" in response.json()["detail"].lower()


def test_bootstrap_profile_capture_attempt_refuses_endpoint_continuity_mismatch(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-bootstrap-endpoint-mismatch",
        idempotency_key="profile-capture-bootstrap-endpoint-mismatch-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.endpoint_assignment_id = None
    db_session.add(command)
    db_session.commit()

    response = _bootstrap_profile_capture_attempt(client, command_id)

    assert response.status_code == 409
    assert "endpoint continuity" in response.json()["detail"].lower()


def test_bootstrap_profile_capture_attempt_reuses_existing_attempt_idempotently(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-bootstrap-reuse",
        idempotency_key="profile-capture-bootstrap-reuse-1",
    )

    first = _bootstrap_profile_capture_attempt(client, command_id)
    second = _bootstrap_profile_capture_attempt(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert second.json()["result"]["reused_existing_attempt"] is True


def test_bootstrap_profile_capture_attempt_persists_durable_bootstrap_artifact(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-bootstrap-artifact",
        idempotency_key="profile-capture-bootstrap-artifact-1",
    )

    response = _bootstrap_profile_capture_attempt(client, command_id, bootstrap_identifier="bootstrap-artifact-1")

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
    assert attempt.execution_metadata["profile_capture_attempt_bootstrap"]["command_id"] == command_id
    assert (
        command.result_summary["profile_capture_attempt_bootstrap"]["command_execution_attempt_id"]
        == str(attempt.id)
    )
