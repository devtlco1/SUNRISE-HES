from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_relay_control_attempt_bootstrap import (
    _bootstrap_relay_control_attempt,
    _create_submitted_relay_control_command,
)


def _handoff_relay_control_to_runtime(
    client,
    command_id: str,
    *,
    handoff_identifier: str = "relay-control-handoff-1",
    executor_identifier: str = "worker-runtime-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/handoff-relay-control-to-runtime",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "handoff_identifier": handoff_identifier,
            "executor_identifier": executor_identifier,
            "handoff_reason": "relay-control-runtime-handoff",
        },
    )


def _create_bootstrapped_relay_control_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    category: str,
    relay_operation: str,
    idempotency_key: str,
) -> tuple[str, str]:
    command_id, _, _, _ = _create_submitted_relay_control_command(
        client,
        db_session,
        command_template_code=command_template_code,
        category=category,
        relay_operation=relay_operation,
        idempotency_key=idempotency_key,
    )
    bootstrap = _bootstrap_relay_control_attempt(client, command_id)
    assert bootstrap.status_code == 200
    return command_id, bootstrap.json()["result"]["command_execution_attempt_id"]


def test_relay_control_runtime_handoff_succeeds_from_valid_bootstrapped_attempt(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-success",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-handoff-success-1",
    )

    response = _handoff_relay_control_to_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["handoff_status"] == "handed_off"
    assert payload["result"]["runtime_relay_control_execution_present"] is True
    assert payload["result"]["reused_existing_handoff"] is False
    assert payload["result"]["reused_existing_runtime_execution"] is False
    assert payload["result"]["relay_control_operation"] == "disconnect"

    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(payload["result"]["job_run_id"]))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert attempt.execution_metadata["runtime_relay_control_execution"]["relay_operation"] == "disconnect"
    assert (
        attempt.execution_metadata["relay_control_runtime_handoff"][
            "runtime_relay_control_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_relay_control_execution"]["relay_control_execution_record_id"]
    )
    assert job_run.status == JobRunStatus.SUCCEEDED
    assert command.current_status == CommandStatus.SUCCEEDED


def test_relay_control_runtime_handoff_refuses_when_bootstrap_artifact_is_missing(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-no-bootstrap",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-handoff-no-bootstrap-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("relay_control_attempt_bootstrap", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_relay_control_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "bootstrap artifact" in response.json()["detail"].lower()


def test_relay_control_runtime_handoff_refuses_when_attempt_is_not_handoff_eligible(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-attempt-terminal",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-handoff-attempt-terminal-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    attempt.status = CommandExecutionAttemptStatus.SUCCEEDED
    attempt.ended_at = None
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_relay_control_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "not runtime-handoff-eligible" in response.json()["detail"].lower()


def test_relay_control_runtime_handoff_refuses_when_request_snapshot_is_incompatible(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-request-snapshot",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-handoff-request-snapshot-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    attempt.request_snapshot = None
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_relay_control_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "request snapshot" in response.json()["detail"].lower()


def test_relay_control_runtime_handoff_refuses_when_endpoint_continuity_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    command_id, _, = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-endpoint-mismatch",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-handoff-endpoint-mismatch-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.endpoint_assignment_id = None
    db_session.add(command)
    db_session.commit()

    response = _handoff_relay_control_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "endpoint continuity" in response.json()["detail"].lower()


def test_relay_control_runtime_handoff_refuses_when_protocol_continuity_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    command_id, _ = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-protocol-mismatch",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-handoff-protocol-mismatch-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.protocol_association_profile_id = None
    db_session.add(command)
    db_session.commit()

    response = _handoff_relay_control_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "protocol continuity" in response.json()["detail"].lower()


def test_relay_control_runtime_handoff_is_idempotent_for_same_context(
    client,
    db_session: Session,
) -> None:
    command_id, _ = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-repeat",
        category="remote_reconnect",
        relay_operation="reconnect",
        idempotency_key="relay-control-runtime-handoff-repeat-1",
    )

    first = _handoff_relay_control_to_runtime(client, command_id)
    second = _handoff_relay_control_to_runtime(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["runtime_relay_control_execution_record_id"]
        == second.json()["result"]["runtime_relay_control_execution_record_id"]
    )
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert second.json()["result"]["reused_existing_handoff"] is True
    assert second.json()["result"]["reused_existing_runtime_execution"] is True


def test_relay_control_runtime_handoff_persists_durable_artifact_mapping(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-handoff-artifact",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-handoff-artifact-1",
    )

    response = _handoff_relay_control_to_runtime(
        client,
        command_id,
        handoff_identifier="relay-control-runtime-handoff-artifact-1",
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(response.json()["result"]["job_run_id"]))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    artifact = attempt.execution_metadata["relay_control_runtime_handoff"]
    assert artifact["command_id"] == command_id
    assert artifact["command_execution_attempt_id"] == attempt_id
    assert artifact["handoff_identifier"] == "relay-control-runtime-handoff-artifact-1"
    assert artifact["relay_control_operation"] == "disconnect"
    assert artifact["runtime_relay_control_execution_present"] is True
    assert (
        command.result_summary["relay_control_runtime_handoff"][
            "runtime_relay_control_execution_record_id"
        ]
        == artifact["runtime_relay_control_execution_record_id"]
    )
    assert (
        job_run.result_summary["relay_control_runtime_handoff"]["handoff_identifier"]
        == artifact["handoff_identifier"]
    )
