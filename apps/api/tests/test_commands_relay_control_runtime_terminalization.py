from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_relay_control_runtime_handoff import (
    _handoff_relay_control_to_runtime,
    _create_bootstrapped_relay_control_command,
)


def _terminalize_relay_control_runtime(
    client,
    command_id: str,
    *,
    terminalization_identifier: str = "relay-control-terminalization-1",
    executor_identifier: str = "worker-runtime-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/terminalize-relay-control-runtime",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "terminalization_identifier": terminalization_identifier,
            "executor_identifier": executor_identifier,
            "terminalization_reason": "relay-control-runtime-terminalization",
        },
    )


def _prepare_terminalizable_relay_control_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    category: str,
    relay_operation: str,
    idempotency_key: str,
) -> tuple[str, str, str]:
    command_id, attempt_id = _create_bootstrapped_relay_control_command(
        client,
        db_session,
        command_template_code=command_template_code,
        category=category,
        relay_operation=relay_operation,
        idempotency_key=idempotency_key,
    )
    handoff = _handoff_relay_control_to_runtime(client, command_id)
    assert handoff.status_code == 200
    return (
        command_id,
        attempt_id,
        handoff.json()["result"]["job_run_id"],
    )


def test_relay_control_runtime_terminalization_succeeds_from_valid_runtime_execution(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-success",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-terminalization-success-1",
    )

    response = _terminalize_relay_control_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["terminalization_status"] == "terminalized"
    assert payload["result"]["relay_control_operation"] == "disconnect"
    assert payload["result"]["relay_control_execution_outcome"] == "succeeded"
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
        attempt.execution_metadata["relay_control_runtime_terminalization"][
            "runtime_relay_control_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_relay_control_execution"][
            "relay_control_execution_record_id"
        ]
    )


def test_relay_control_runtime_terminalization_refuses_when_handoff_artifact_is_missing(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-no-handoff",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-terminalization-no-handoff-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("relay_control_runtime_handoff", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_relay_control_runtime(client, command_id)

    assert response.status_code == 409
    assert "runtime handoff artifact" in response.json()["detail"].lower()


def test_relay_control_runtime_terminalization_refuses_when_runtime_execution_is_not_yet_terminalizable(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-not-ready",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-terminalization-not-ready-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("runtime_relay_control_execution", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_relay_control_runtime(client, command_id)

    assert response.status_code == 409
    assert "not yet terminalizable" in response.json()["detail"].lower()


def test_relay_control_runtime_terminalization_refuses_when_runtime_execution_linkage_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-linkage",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-terminalization-linkage-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    runtime_relay_control_execution = dict(execution_metadata["runtime_relay_control_execution"])
    runtime_relay_control_execution["command_attempt_id"] = str(UUID(int=1))
    execution_metadata["runtime_relay_control_execution"] = runtime_relay_control_execution
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_relay_control_runtime(client, command_id)

    assert response.status_code == 409
    assert "execution linkage" in response.json()["detail"].lower()


def test_relay_control_runtime_terminalization_is_idempotent_for_same_runtime_context(
    client,
    db_session: Session,
) -> None:
    command_id, _, _ = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-repeat",
        category="remote_reconnect",
        relay_operation="reconnect",
        idempotency_key="relay-control-runtime-terminalization-repeat-1",
    )

    first = _terminalize_relay_control_runtime(client, command_id)
    second = _terminalize_relay_control_runtime(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["runtime_relay_control_execution_record_id"]
        == second.json()["result"]["runtime_relay_control_execution_record_id"]
    )
    assert second.json()["result"]["reused_existing_terminalization"] is True


def test_relay_control_runtime_terminalization_persists_durable_artifact_mapping(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-artifact",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-terminalization-artifact-1",
    )

    response = _terminalize_relay_control_runtime(
        client,
        command_id,
        terminalization_identifier="relay-control-terminalization-artifact-1",
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(job_run_id))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    artifact = attempt.execution_metadata["relay_control_runtime_terminalization"]
    assert artifact["command_id"] == command_id
    assert artifact["command_execution_attempt_id"] == attempt_id
    assert artifact["job_run_id"] == job_run_id
    assert artifact["terminalization_identifier"] == "relay-control-terminalization-artifact-1"
    assert (
        command.result_summary["relay_control_runtime_terminalization"][
            "runtime_relay_control_execution_record_id"
        ]
        == artifact["runtime_relay_control_execution_record_id"]
    )
    assert (
        job_run.result_summary["relay_control_runtime_terminalization"][
            "relay_control_execution_outcome"
        ]
        == artifact["relay_control_execution_outcome"]
    )


def test_relay_control_runtime_terminalization_maps_timed_out_runtime_execution_to_timed_out_final_state(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-timeout",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-terminalization-timeout-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    runtime_relay_control_execution = dict(execution_metadata["runtime_relay_control_execution"])
    runtime_relay_control_execution["execution_outcome"] = "timed_out"
    runtime_relay_control_execution["error_detail"] = "simulated timed out relay-control execution"
    execution_metadata["runtime_relay_control_execution"] = runtime_relay_control_execution
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_relay_control_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["attempt_final_status"] == "timed_out"
    assert payload["result"]["command_final_status"] == "timed_out"
    assert payload["result"]["job_run_final_status"] == "timed_out"
    assert payload["result"]["terminalization_reason_category"] == "timed_out"

    refreshed_attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    refreshed_command = db_session.get(MeterCommand, UUID(command_id))
    refreshed_job_run = db_session.get(JobRun, UUID(job_run_id))
    assert refreshed_attempt is not None
    assert refreshed_command is not None
    assert refreshed_job_run is not None
    assert refreshed_attempt.status == CommandExecutionAttemptStatus.TIMED_OUT
    assert refreshed_command.current_status == CommandStatus.TIMED_OUT
    assert refreshed_job_run.status == JobRunStatus.TIMED_OUT


def test_relay_control_runtime_terminalization_maps_non_success_runtime_execution_to_failed_final_state(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_relay_control_command(
        client,
        db_session,
        command_template_code="relay-control-runtime-terminalization-failed",
        category="remote_disconnect",
        relay_operation="disconnect",
        idempotency_key="relay-control-runtime-terminalization-failed-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    runtime_relay_control_execution = dict(execution_metadata["runtime_relay_control_execution"])
    runtime_relay_control_execution["execution_outcome"] = "failed"
    runtime_relay_control_execution["adapter_acknowledgment_state"] = "rejected"
    runtime_relay_control_execution["protocol_stage_outcome"] = "relay_operation_failed"
    runtime_relay_control_execution["error_detail"] = "simulated rejected relay-control execution"
    execution_metadata["runtime_relay_control_execution"] = runtime_relay_control_execution
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_relay_control_runtime(client, command_id)

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
