from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_on_demand_read_runtime_handoff import (
    _create_bootstrapped_on_demand_read_command,
    _handoff_on_demand_read_to_runtime,
)


def _terminalize_on_demand_read_runtime(
    client,
    command_id: str,
    *,
    terminalization_identifier: str = "on-demand-read-terminalization-1",
    executor_identifier: str = "worker-runtime-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/terminalize-on-demand-read-runtime",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "terminalization_identifier": terminalization_identifier,
            "executor_identifier": executor_identifier,
            "terminalization_reason": "on-demand-read-runtime-terminalization",
        },
    )


def _prepare_terminalizable_on_demand_read_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    idempotency_key: str,
) -> tuple[str, str, str]:
    command_id, attempt_id = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code=command_template_code,
        idempotency_key=idempotency_key,
    )
    handoff = _handoff_on_demand_read_to_runtime(client, command_id)
    assert handoff.status_code == 200
    return (
        command_id,
        attempt_id,
        handoff.json()["result"]["job_run_id"],
    )


def test_on_demand_read_runtime_terminalization_succeeds_from_valid_runtime_execution(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-success",
        idempotency_key="on-demand-read-runtime-terminalization-success-1",
    )

    response = _terminalize_on_demand_read_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["terminalization_status"] == "terminalized"
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["result"]["on_demand_read_execution_outcome"] == "succeeded"
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
        attempt.execution_metadata["on_demand_read_runtime_terminalization"][
            "runtime_on_demand_read_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_on_demand_read_execution"][
            "on_demand_read_execution_record_id"
        ]
    )


def test_on_demand_read_runtime_terminalization_refuses_when_handoff_artifact_is_missing(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-no-handoff",
        idempotency_key="on-demand-read-runtime-terminalization-no-handoff-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("on_demand_read_runtime_handoff", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_on_demand_read_runtime(client, command_id)

    assert response.status_code == 409
    assert "runtime handoff artifact" in response.json()["detail"].lower()


def test_on_demand_read_runtime_terminalization_refuses_when_runtime_execution_is_not_yet_terminalizable(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-not-ready",
        idempotency_key="on-demand-read-runtime-terminalization-not-ready-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    execution_metadata.pop("runtime_on_demand_read_execution", None)
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_on_demand_read_runtime(client, command_id)

    assert response.status_code == 409
    assert "not yet terminalizable" in response.json()["detail"].lower()


def test_on_demand_read_runtime_terminalization_refuses_when_runtime_execution_linkage_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, _ = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-linkage",
        idempotency_key="on-demand-read-runtime-terminalization-linkage-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    runtime_on_demand_read_execution = dict(execution_metadata["runtime_on_demand_read_execution"])
    runtime_on_demand_read_execution["command_attempt_id"] = str(UUID(int=1))
    execution_metadata["runtime_on_demand_read_execution"] = runtime_on_demand_read_execution
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_on_demand_read_runtime(client, command_id)

    assert response.status_code == 409
    assert "execution linkage" in response.json()["detail"].lower()


def test_on_demand_read_runtime_terminalization_is_idempotent_for_same_runtime_context(
    client,
    db_session: Session,
) -> None:
    command_id, _, _ = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-repeat",
        idempotency_key="on-demand-read-runtime-terminalization-repeat-1",
    )

    first = _terminalize_on_demand_read_runtime(client, command_id)
    second = _terminalize_on_demand_read_runtime(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["runtime_on_demand_read_execution_record_id"]
        == second.json()["result"]["runtime_on_demand_read_execution_record_id"]
    )
    assert second.json()["result"]["reused_existing_terminalization"] is True


def test_on_demand_read_runtime_terminalization_persists_durable_artifact_mapping(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-artifact",
        idempotency_key="on-demand-read-runtime-terminalization-artifact-1",
    )

    response = _terminalize_on_demand_read_runtime(
        client,
        command_id,
        terminalization_identifier="on-demand-read-terminalization-artifact-1",
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(job_run_id))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    artifact = attempt.execution_metadata["on_demand_read_runtime_terminalization"]
    assert artifact["command_id"] == command_id
    assert artifact["command_execution_attempt_id"] == attempt_id
    assert artifact["job_run_id"] == job_run_id
    assert artifact["terminalization_identifier"] == "on-demand-read-terminalization-artifact-1"
    assert artifact["on_demand_read_operation"] == "read_billing_snapshot"
    assert artifact["snapshot_type"] == "billing"
    assert (
        command.result_summary["on_demand_read_runtime_terminalization"][
            "runtime_on_demand_read_execution_record_id"
        ]
        == artifact["runtime_on_demand_read_execution_record_id"]
    )
    assert (
        job_run.result_summary["on_demand_read_runtime_terminalization"][
            "on_demand_read_execution_outcome"
        ]
        == artifact["on_demand_read_execution_outcome"]
    )


def test_on_demand_read_runtime_terminalization_maps_timed_out_runtime_execution_to_timed_out_final_state(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-timeout",
        idempotency_key="on-demand-read-runtime-terminalization-timeout-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    runtime_on_demand_read_execution = dict(execution_metadata["runtime_on_demand_read_execution"])
    runtime_on_demand_read_execution["execution_outcome"] = "timed_out"
    runtime_on_demand_read_execution["error_detail"] = "simulated timed out on-demand-read execution"
    execution_metadata["runtime_on_demand_read_execution"] = runtime_on_demand_read_execution
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_on_demand_read_runtime(client, command_id)

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


def test_on_demand_read_runtime_terminalization_maps_non_success_runtime_execution_to_failed_final_state(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id, job_run_id = _prepare_terminalizable_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-terminalization-failed",
        idempotency_key="on-demand-read-runtime-terminalization-failed-1",
    )
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    runtime_on_demand_read_execution = dict(execution_metadata["runtime_on_demand_read_execution"])
    runtime_on_demand_read_execution["execution_outcome"] = "failed"
    runtime_on_demand_read_execution["adapter_acknowledgment_state"] = "rejected"
    runtime_on_demand_read_execution["protocol_stage_outcome"] = "billing_snapshot_failed"
    runtime_on_demand_read_execution["error_detail"] = "simulated rejected on-demand-read execution"
    execution_metadata["runtime_on_demand_read_execution"] = runtime_on_demand_read_execution
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()

    response = _terminalize_on_demand_read_runtime(client, command_id)

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
