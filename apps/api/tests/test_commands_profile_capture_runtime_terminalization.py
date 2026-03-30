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


def _terminalize_profile_capture_runtime(
    client,
    command_id: str,
    *,
    terminalization_identifier: str = "profile-capture-terminalization-1",
    executor_identifier: str = "worker-runtime-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/terminalize-profile-capture-runtime",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "terminalization_identifier": terminalization_identifier,
            "executor_identifier": executor_identifier,
            "terminalization_reason": "profile-capture-runtime-terminalization",
        },
    )


def _prepare_terminalizable_profile_capture_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    idempotency_key: str,
) -> tuple[str, str, str]:
    command_id, _, _, _, _ = _create_submitted_profile_capture_command(
        client,
        db_session,
        command_template_code=command_template_code,
        idempotency_key=idempotency_key,
    )
    bootstrap = _bootstrap_profile_capture_attempt(client, command_id)
    assert bootstrap.status_code == 200
    handoff = _handoff_profile_capture_to_runtime(client, command_id)
    assert handoff.status_code == 200
    payload = handoff.json()["result"]
    return (
        command_id,
        payload["command_execution_attempt_id"],
        payload["job_run_id"],
    )


def test_profile_capture_runtime_terminalization_succeeds_from_valid_runtime_execution(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-terminalization-success",
        idempotency_key="profile-capture-runtime-terminalization-success-1",
    )

    response = _terminalize_profile_capture_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["terminalization_status"] == "terminalized"
    assert payload["result"]["runtime_capture_load_profile_terminal_status"] == "acknowledged"
    assert payload["result"]["attempt_final_status"] == "succeeded"
    assert payload["result"]["command_final_status"] == "succeeded"
    assert payload["result"]["job_run_final_status"] == "succeeded"
    assert payload["result"]["reused_existing_terminalization"] is False

    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(job_run_id))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert command.current_status == CommandStatus.SUCCEEDED
    assert job_run.status == JobRunStatus.SUCCEEDED
    assert (
        attempt.execution_metadata["profile_capture_runtime_terminalization"][
            "runtime_profile_read_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_profile_read_execution"]["profile_read_execution_record_id"]
    )


def test_profile_capture_runtime_terminalization_refuses_when_handoff_artifact_is_missing(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-terminalization-no-handoff",
        idempotency_key="profile-capture-runtime-terminalization-no-handoff-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("profile_capture_runtime_handoff", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_profile_capture_runtime(client, command_id)

    assert response.status_code == 409
    assert "runtime handoff artifact" in response.json()["detail"].lower()


def test_profile_capture_runtime_terminalization_refuses_when_runtime_execution_is_not_yet_terminalizable(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-terminalization-not-ready",
        idempotency_key="profile-capture-runtime-terminalization-not-ready-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("runtime_profile_read_execution", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_profile_capture_runtime(client, command_id)

    assert response.status_code == 409
    assert "not yet terminalizable" in response.json()["detail"].lower()


def test_profile_capture_runtime_terminalization_refuses_when_terminal_status_linkage_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-terminalization-linkage",
        idempotency_key="profile-capture-runtime-terminalization-linkage-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    terminal_status = dict(execution_metadata["runtime_capture_load_profile_terminal_status"])
    terminal_status["profile_read_execution_record_id"] = "different-profile-read-record"
    execution_metadata["runtime_capture_load_profile_terminal_status"] = terminal_status
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_profile_capture_runtime(client, command_id)

    assert response.status_code == 409
    assert "terminal status linkage" in response.json()["detail"].lower()


def test_profile_capture_runtime_terminalization_is_idempotent_for_same_runtime_context(
    client,
    db_session: Session,
) -> None:
    command_id, _, _ = _prepare_terminalizable_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-terminalization-repeat",
        idempotency_key="profile-capture-runtime-terminalization-repeat-1",
    )

    first = _terminalize_profile_capture_runtime(client, command_id)
    second = _terminalize_profile_capture_runtime(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["runtime_profile_read_execution_record_id"]
        == second.json()["result"]["runtime_profile_read_execution_record_id"]
    )
    assert second.json()["result"]["reused_existing_terminalization"] is True


def test_profile_capture_runtime_terminalization_persists_durable_artifact_mapping(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-terminalization-artifact",
        idempotency_key="profile-capture-runtime-terminalization-artifact-1",
    )

    response = _terminalize_profile_capture_runtime(
        client,
        command_id,
        terminalization_identifier="profile-capture-terminalization-artifact-1",
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(job_run_id))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    artifact = attempt.execution_metadata["profile_capture_runtime_terminalization"]
    assert artifact["command_id"] == command_id
    assert artifact["command_execution_attempt_id"] == attempt_id
    assert artifact["job_run_id"] == job_run_id
    assert artifact["terminalization_identifier"] == "profile-capture-terminalization-artifact-1"
    assert (
        command.result_summary["profile_capture_runtime_terminalization"][
            "runtime_profile_read_execution_record_id"
        ]
        == artifact["runtime_profile_read_execution_record_id"]
    )
    assert (
        job_run.result_summary["profile_capture_runtime_terminalization"][
            "runtime_capture_load_profile_terminal_status"
        ]
        == artifact["runtime_capture_load_profile_terminal_status"]
    )


def test_profile_capture_runtime_terminalization_maps_failed_runtime_execution_to_failed_final_state(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_profile_capture_command(
        client,
        db_session,
        command_template_code="profile-capture-runtime-terminalization-failed",
        idempotency_key="profile-capture-runtime-terminalization-failed-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    runtime_profile_read_execution = dict(execution_metadata["runtime_profile_read_execution"])
    runtime_profile_read_execution["execution_outcome"] = "failed"
    runtime_profile_read_execution["error_detail"] = (
        "simulated rejected profile-capture runtime execution"
    )
    terminal_status = dict(execution_metadata["runtime_capture_load_profile_terminal_status"])
    terminal_status["terminal_status"] = "rejected"
    terminal_status["summary"] = (
        "simulated rejected profile-capture terminal status"
    )
    execution_metadata["runtime_profile_read_execution"] = runtime_profile_read_execution
    execution_metadata["runtime_capture_load_profile_terminal_status"] = terminal_status
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_profile_capture_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["attempt_final_status"] == "failed"
    assert payload["result"]["command_final_status"] == "failed"
    assert payload["result"]["job_run_final_status"] == "failed"
    assert payload["result"]["terminalization_reason_category"] == "failed"

    refreshed_attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    refreshed_command = db_session.get(MeterCommand, UUID(command_id))
    refreshed_job_run = db_session.get(JobRun, UUID(job_run_id))
    assert refreshed_attempt is not None
    assert refreshed_command is not None
    assert refreshed_job_run is not None
    assert refreshed_attempt.status == CommandExecutionAttemptStatus.FAILED
    assert refreshed_command.current_status == CommandStatus.FAILED
    assert refreshed_job_run.status == JobRunStatus.FAILED
