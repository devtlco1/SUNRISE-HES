from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_profile_capture_attempt_bootstrap import (
    _bootstrap_profile_capture_attempt,
    _create_submitted_profile_capture_command,
)
from tests.test_commands_profile_capture_runtime_handoff import (
    _handoff_profile_capture_to_runtime,
)
from tests.test_commands_profile_capture_runtime_terminalization import (
    _terminalize_profile_capture_runtime,
)


def _execute_profile_capture_in_process(
    client,
    command_id: str,
    *,
    orchestration_identifier: str = "profile-capture-orchestration-1",
    executor_identifier: str = "worker-runtime-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/execute-profile-capture-in-process",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "orchestration_identifier": orchestration_identifier,
            "executor_identifier": executor_identifier,
            "orchestration_reason": "profile-capture-execution-orchestration",
        },
    )


def test_profile_capture_execution_orchestration_executes_end_to_end_from_valid_submitted_command(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-orchestration-success",
        idempotency_key="profile-capture-orchestration-success-1",
    )

    response = _execute_profile_capture_in_process(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["orchestration_status"] == "orchestrated"
    assert payload["result"]["terminalization_artifact_present"] is True
    assert payload["result"]["reused_existing_orchestration"] is False

    attempt = db_session.get(
        CommandExecutionAttempt,
        UUID(payload["result"]["command_execution_attempt_id"]),
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(payload["result"]["job_run_id"]))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert command.current_status == CommandStatus.SUCCEEDED
    assert job_run.status == JobRunStatus.SUCCEEDED
    assert (
        attempt.execution_metadata["profile_capture_execution_orchestration"][
            "runtime_profile_read_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_profile_read_execution"]["profile_read_execution_record_id"]
    )
    assert (
        attempt.execution_metadata["profile_capture_runtime_terminalization"][
            "terminalization_identifier"
        ]
        == "profile-capture-orchestration-1"
    )


def test_profile_capture_execution_orchestration_refuses_when_command_is_not_execution_eligible(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-orchestration-ineligible",
        idempotency_key="profile-capture-orchestration-ineligible-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _execute_profile_capture_in_process(client, command_id)

    assert response.status_code == 409
    assert "not execution-eligible" in response.json()["detail"].lower()


def test_profile_capture_execution_orchestration_refuses_when_normalized_payload_is_missing(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-orchestration-missing-normalized",
        idempotency_key="profile-capture-orchestration-missing-normalized-1",
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.normalized_payload = None
    db_session.add(command)
    db_session.commit()

    response = _execute_profile_capture_in_process(client, command_id)

    assert response.status_code == 409
    assert "missing normalized payload" in response.json()["detail"].lower()


def test_profile_capture_execution_orchestration_refuses_when_incompatible_prior_finalized_execution_exists(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-orchestration-prior-finalized",
        idempotency_key="profile-capture-orchestration-prior-finalized-1",
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id, bootstrap_identifier="manual-bootstrap-1")
    assert bootstrap.status_code == 200
    handoff = _handoff_profile_capture_to_runtime(
        client,
        command_id,
        handoff_identifier="manual-handoff-1",
    )
    assert handoff.status_code == 200
    terminalization = _terminalize_profile_capture_runtime(
        client,
        command_id,
        terminalization_identifier="manual-terminalization-1",
    )
    assert terminalization.status_code == 200

    response = _execute_profile_capture_in_process(
        client,
        command_id,
        orchestration_identifier="profile-capture-orchestration-prior-finalized-1",
    )

    assert response.status_code == 409
    assert "incompatible prior finalized execution" in response.json()["detail"].lower()


def test_profile_capture_execution_orchestration_is_idempotent_for_same_context(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-orchestration-repeat",
        idempotency_key="profile-capture-orchestration-repeat-1",
    )

    first = _execute_profile_capture_in_process(client, command_id)
    second = _execute_profile_capture_in_process(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["runtime_profile_read_execution_record_id"]
        == second.json()["result"]["runtime_profile_read_execution_record_id"]
    )
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert second.json()["result"]["reused_existing_orchestration"] is True


def test_profile_capture_execution_orchestration_persists_durable_artifact_mapping(
    client,
    db_session: Session,
) -> None:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-orchestration-artifact",
        idempotency_key="profile-capture-orchestration-artifact-1",
    )

    response = _execute_profile_capture_in_process(
        client,
        command_id,
        orchestration_identifier="profile-capture-orchestration-artifact-1",
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
    artifact = attempt.execution_metadata["profile_capture_execution_orchestration"]
    assert artifact["command_id"] == command_id
    assert artifact["command_execution_attempt_id"] == str(attempt.id)
    assert artifact["job_run_id"] == str(job_run.id)
    assert artifact["orchestration_identifier"] == "profile-capture-orchestration-artifact-1"
    assert artifact["terminalization_artifact_present"] is True
    assert (
        command.result_summary["profile_capture_execution_orchestration"][
            "runtime_profile_read_execution_record_id"
        ]
        == artifact["runtime_profile_read_execution_record_id"]
    )
    assert (
        job_run.result_summary["profile_capture_execution_orchestration"][
            "orchestration_identifier"
        ]
        == artifact["orchestration_identifier"]
    )
