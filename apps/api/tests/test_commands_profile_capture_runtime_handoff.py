from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_commands_profile_capture_attempt_bootstrap import (
    _bootstrap_profile_capture_attempt,
    _create_submitted_profile_capture_command,
)


def _handoff_profile_capture_to_runtime(
    client,
    command_id: str,
    *,
    handoff_identifier: str = "profile-capture-handoff-1",
    executor_identifier: str = "worker-runtime-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/handoff-profile-capture-to-runtime",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "handoff_identifier": handoff_identifier,
            "executor_identifier": executor_identifier,
            "handoff_reason": "profile-capture-runtime-handoff",
        },
    )


def _load_active_attempt(db_session: Session, command_id: str) -> CommandExecutionAttempt:
    attempt = db_session.scalar(
        select(CommandExecutionAttempt)
        .where(
            CommandExecutionAttempt.meter_command_id == UUID(command_id),
            CommandExecutionAttempt.ended_at.is_(None),
        )
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )
    assert attempt is not None
    return attempt


def test_profile_capture_runtime_handoff_executes_runtime_profile_read_from_bootstrapped_attempt(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-success",
        idempotency_key="profile-capture-runtime-handoff-success-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200

    response = _handoff_profile_capture_to_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["handoff_status"] == "handed_off"
    assert payload["result"]["runtime_profile_read_execution_present"] is True
    assert payload["result"]["runtime_profile_read_execution_record_id"] is not None
    assert payload["result"]["reused_existing_handoff"] is False
    assert payload["result"]["reused_existing_runtime_execution"] is False
    assert payload["job_run"]["id"] == payload["result"]["job_run_id"]
    assert payload["created_or_existing_attempt"]["job_run_id"] == payload["job_run"]["id"]

    attempt = db_session.get(
        CommandExecutionAttempt,
        UUID(payload["result"]["command_execution_attempt_id"]),
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(payload["result"]["job_run_id"]))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert attempt.execution_metadata["profile_capture_runtime_handoff"]["handoff_identifier"] == (
        "profile-capture-handoff-1"
    )
    assert attempt.execution_metadata["runtime_profile_read_execution"]["status"] == "completed"
    assert (
        attempt.execution_metadata["runtime_capture_load_profile_execution_digest"][
            "final_execution_category"
        ]
        == "completed"
    )
    assert (
        command.result_summary["profile_capture_runtime_handoff"]["runtime_profile_read_execution_record_id"]
        == attempt.execution_metadata["runtime_profile_read_execution"]["profile_read_execution_record_id"]
    )
    assert (
        job_run.result_summary["profile_capture_runtime_handoff"]["runtime_profile_read_execution_present"]
        is True
    )


def test_profile_capture_runtime_handoff_refuses_when_bootstrap_artifact_is_missing(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-no-bootstrap",
        idempotency_key="profile-capture-runtime-handoff-no-bootstrap-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200
    attempt = _load_active_attempt(db_session, command_id)
    attempt.execution_metadata = {}
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_profile_capture_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "bootstrap artifact" in response.json()["detail"].lower()


def test_profile_capture_runtime_handoff_refuses_when_attempt_is_not_handoff_eligible(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-attempt-state",
        idempotency_key="profile-capture-runtime-handoff-attempt-state-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200
    attempt = _load_active_attempt(db_session, command_id)
    attempt.status = CommandExecutionAttemptStatus.RUNNING
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_profile_capture_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "not runtime-handoff-eligible" in response.json()["detail"].lower()


def test_profile_capture_runtime_handoff_refuses_when_request_snapshot_is_incompatible(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-bad-snapshot",
        idempotency_key="profile-capture-runtime-handoff-bad-snapshot-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200
    attempt = _load_active_attempt(db_session, command_id)
    attempt.request_snapshot = None
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_profile_capture_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "request snapshot" in response.json()["detail"].lower()


def test_profile_capture_runtime_handoff_refuses_when_endpoint_continuity_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-endpoint-mismatch",
        idempotency_key="profile-capture-runtime-handoff-endpoint-mismatch-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200
    attempt = _load_active_attempt(db_session, command_id)
    attempt.endpoint_id = None
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_profile_capture_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "endpoint continuity" in response.json()["detail"].lower()


def test_profile_capture_runtime_handoff_refuses_when_protocol_continuity_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-protocol-mismatch",
        idempotency_key="profile-capture-runtime-handoff-protocol-mismatch-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.protocol_association_profile_id = None
    db_session.add(command)
    db_session.commit()

    response = _handoff_profile_capture_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "protocol continuity" in response.json()["detail"].lower()


def test_profile_capture_runtime_handoff_is_idempotent_for_same_handoff_context(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-repeat",
        idempotency_key="profile-capture-runtime-handoff-repeat-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200

    first = _handoff_profile_capture_to_runtime(client, command_id)
    second = _handoff_profile_capture_to_runtime(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["runtime_profile_read_execution_record_id"]
        == second.json()["result"]["runtime_profile_read_execution_record_id"]
    )
    assert first.json()["result"]["job_run_id"] == second.json()["result"]["job_run_id"]
    assert second.json()["result"]["reused_existing_handoff"] is True
    assert second.json()["result"]["reused_existing_runtime_execution"] is True


def test_profile_capture_runtime_handoff_persists_durable_artifact_mapping(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-handoff-artifact",
        idempotency_key="profile-capture-runtime-handoff-artifact-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200

    response = _handoff_profile_capture_to_runtime(
        client,
        command_id,
        handoff_identifier="profile-capture-handoff-artifact-1",
    )

    assert response.status_code == 200
    attempt = db_session.get(
        CommandExecutionAttempt,
        UUID(response.json()["result"]["command_execution_attempt_id"]),
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(response.json()["result"]["job_run_id"]))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    artifact = attempt.execution_metadata["profile_capture_runtime_handoff"]
    assert artifact["command_id"] == command_id
    assert artifact["command_execution_attempt_id"] == str(attempt.id)
    assert artifact["job_run_id"] == str(job_run.id)
    assert artifact["handoff_identifier"] == "profile-capture-handoff-artifact-1"
    assert artifact["runtime_profile_read_execution_record_id"] == (
        attempt.execution_metadata["runtime_profile_read_execution"]["profile_read_execution_record_id"]
    )
    assert (
        command.result_summary["profile_capture_runtime_handoff"]["runtime_profile_read_execution_record_id"]
        == artifact["runtime_profile_read_execution_record_id"]
    )
    assert (
        job_run.result_summary["profile_capture_runtime_handoff"]["runtime_profile_read_execution_record_id"]
        == artifact["runtime_profile_read_execution_record_id"]
    )
