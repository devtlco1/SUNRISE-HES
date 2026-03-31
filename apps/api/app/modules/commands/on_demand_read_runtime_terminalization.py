from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import (
    CommandCategory,
    CommandExecutionAttemptStatus,
    CommandStatus,
    OnDemandReadCommandOperation,
)
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.schemas import (
    OnDemandReadRuntimeTerminalizationRequest,
    OnDemandReadRuntimeTerminalizationResponse,
    OnDemandReadRuntimeTerminalizationResult,
)
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from app.modules.jobs.service import serialize_job_run
from app.modules.readings.enums import SnapshotType
from app.modules.commands.service import (
    get_meter_command,
    serialize_command_attempt,
    serialize_meter_command,
)
from app.runtime.contracts import (
    RuntimeCommandOutcome,
    RuntimeOnDemandReadAdapterAcknowledgmentState,
    RuntimeOnDemandReadExecutionResult,
    RuntimeOnDemandReadExecutionStatus,
    RuntimeOnDemandReadProtocolStageOutcome,
)
from app.runtime.services.runtime_artifact_utils import merge_runtime_metadata


def terminalize_on_demand_read_runtime_execution(
    session: Session,
    *,
    command_id: uuid.UUID,
    payload: OnDemandReadRuntimeTerminalizationRequest,
) -> OnDemandReadRuntimeTerminalizationResponse:
    command = get_meter_command(session, command_id)
    attempt = _load_latest_on_demand_read_attempt(session, command_id=command.id)
    existing_terminalization = _load_on_demand_read_runtime_terminalization(
        attempt.execution_metadata if attempt is not None else None
    )
    if existing_terminalization is not None:
        return _build_existing_terminalization_response(
            session,
            command=command,
            attempt=attempt,
            payload=payload,
            terminalization_record=existing_terminalization,
        )

    if command.command_template.category != CommandCategory.ON_DEMAND_READ:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the on-demand-read runtime terminalization slice.",
        )
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read command does not have a runtime-backed attempt for terminalization.",
        )

    handoff_record = _load_on_demand_read_runtime_handoff(attempt.execution_metadata)
    if handoff_record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read attempt is missing the runtime handoff artifact required for terminalization.",
        )
    runtime_execution = _load_runtime_on_demand_read_execution(attempt.execution_metadata)
    if runtime_execution is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read attempt is not yet terminalizable because the runtime on-demand-read execution artifact is missing.",
        )
    _validate_on_demand_read_terminalization_context(
        command=command,
        attempt=attempt,
        handoff_record=handoff_record,
        runtime_execution=runtime_execution,
        executor_identifier=payload.executor_identifier,
    )
    mapping = _resolve_terminalization_mapping(runtime_execution=runtime_execution)
    now = datetime.now(UTC)
    terminalization_record = _build_on_demand_read_runtime_terminalization_record(
        command=command,
        attempt=attempt,
        runtime_execution=runtime_execution,
        payload=payload,
        mapping=mapping,
        terminalized_at=now,
    )
    attempt.execution_metadata = merge_runtime_metadata(
        attempt.execution_metadata,
        {"on_demand_read_runtime_terminalization": terminalization_record},
    )
    result_summary = merge_runtime_metadata(
        command.result_summary,
        {"on_demand_read_runtime_terminalization": terminalization_record},
    )
    _apply_on_demand_read_terminal_state(
        attempt=attempt,
        command=command,
        job_run=session.get(JobRun, attempt.job_run_id) if attempt.job_run_id is not None else None,
        runtime_execution=runtime_execution,
        mapping=mapping,
        result_summary=result_summary,
        terminalized_at=now,
    )
    session.add(command)
    session.add(attempt)
    refreshed_job_run = session.get(JobRun, attempt.job_run_id) if attempt.job_run_id is not None else None
    if refreshed_job_run is not None:
        session.add(refreshed_job_run)
    session.commit()
    session.refresh(attempt)
    session.refresh(command)
    if refreshed_job_run is not None:
        session.refresh(refreshed_job_run)
    return _build_terminalization_response(
        command=command,
        attempt=attempt,
        job_run=refreshed_job_run,
        terminalization_record=terminalization_record,
        reused_existing_terminalization=False,
    )


def _load_latest_on_demand_read_attempt(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandExecutionAttempt | None:
    return session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command_id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )


def _build_existing_terminalization_response(
    session: Session,
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
    payload: OnDemandReadRuntimeTerminalizationRequest,
    terminalization_record: dict[str, object],
) -> OnDemandReadRuntimeTerminalizationResponse:
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read runtime terminalization artifact references a missing attempt.",
        )
    if terminalization_record.get("terminalization_identifier") != payload.terminalization_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read runtime terminalization already exists for another terminalization identifier.",
        )
    if terminalization_record.get("executor_identifier") != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read runtime terminalization is already owned by another executor.",
        )
    job_run = session.get(JobRun, attempt.job_run_id) if attempt.job_run_id is not None else None
    return _build_terminalization_response(
        command=command,
        attempt=attempt,
        job_run=job_run,
        terminalization_record=terminalization_record,
        reused_existing_terminalization=True,
    )


def _validate_on_demand_read_terminalization_context(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    handoff_record: dict[str, object],
    runtime_execution: RuntimeOnDemandReadExecutionResult,
    executor_identifier: str,
) -> None:
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read attempt is not linked to a job run for terminalization.",
        )
    if handoff_record.get("handoff_status") != "handed_off":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read runtime handoff artifact is invalid for terminalization.",
        )
    if handoff_record.get("executor_identifier") != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read runtime handoff is owned by another executor.",
        )
    if runtime_execution.command_category != CommandCategory.ON_DEMAND_READ:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime on-demand-read execution is incompatible with on-demand-read terminalization.",
        )
    if str(runtime_execution.related_command_id) != str(command.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime on-demand-read execution linkage is inconsistent with the related command.",
        )
    if str(runtime_execution.command_attempt_id) != str(attempt.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime on-demand-read execution linkage is inconsistent with the command attempt.",
        )
    if str(runtime_execution.job_run_id) != str(attempt.job_run_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime on-demand-read execution linkage is inconsistent with the job run.",
        )
    if runtime_execution.on_demand_read_recorded_by_executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime on-demand-read execution is owned by another executor.",
        )
    if runtime_execution.status != RuntimeOnDemandReadExecutionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read runtime execution is not yet terminalizable.",
        )
    handoff_runtime_execution_record_id = handoff_record.get(
        "runtime_on_demand_read_execution_record_id"
    )
    if (
        handoff_runtime_execution_record_id is not None
        and str(handoff_runtime_execution_record_id)
        != runtime_execution.on_demand_read_execution_record_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime handoff artifact is inconsistent with the recorded runtime on-demand-read execution.",
        )


def _resolve_terminalization_mapping(
    *,
    runtime_execution: RuntimeOnDemandReadExecutionResult,
) -> dict[str, object]:
    if (
        runtime_execution.execution_outcome == RuntimeCommandOutcome.SUCCEEDED
        and runtime_execution.adapter_acknowledgment_state
        == RuntimeOnDemandReadAdapterAcknowledgmentState.ACCEPTED
        and runtime_execution.protocol_stage_outcome
        == RuntimeOnDemandReadProtocolStageOutcome.BILLING_SNAPSHOT_COMPLETED
    ):
        return {
            "terminalization_reason_category": "succeeded",
            "attempt_final_status": CommandExecutionAttemptStatus.SUCCEEDED,
            "command_final_status": CommandStatus.SUCCEEDED,
            "job_run_final_status": JobRunStatus.SUCCEEDED,
            "error_code": None,
            "error_message": None,
        }
    if runtime_execution.execution_outcome == RuntimeCommandOutcome.TIMED_OUT:
        return {
            "terminalization_reason_category": "timed_out",
            "attempt_final_status": CommandExecutionAttemptStatus.TIMED_OUT,
            "command_final_status": CommandStatus.TIMED_OUT,
            "job_run_final_status": JobRunStatus.TIMED_OUT,
            "error_code": "ON_DEMAND_READ_RUNTIME_TIMED_OUT",
            "error_message": runtime_execution.error_detail or runtime_execution.summary,
        }
    return {
        "terminalization_reason_category": "failed",
        "attempt_final_status": CommandExecutionAttemptStatus.FAILED,
        "command_final_status": CommandStatus.FAILED,
        "job_run_final_status": JobRunStatus.FAILED,
        "error_code": f"ON_DEMAND_READ_{runtime_execution.execution_outcome.value.upper()}",
        "error_message": runtime_execution.error_detail or runtime_execution.summary,
    }


def _build_on_demand_read_runtime_terminalization_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    runtime_execution: RuntimeOnDemandReadExecutionResult,
    payload: OnDemandReadRuntimeTerminalizationRequest,
    mapping: dict[str, object],
    terminalized_at: datetime,
) -> dict[str, object]:
    return {
        "terminalization_status": "terminalized",
        "command_id": str(command.id),
        "command_execution_attempt_id": str(attempt.id),
        "job_run_id": str(attempt.job_run_id) if attempt.job_run_id is not None else None,
        "terminalization_identifier": payload.terminalization_identifier,
        "executor_identifier": payload.executor_identifier,
        "runtime_on_demand_read_execution_record_id": runtime_execution.on_demand_read_execution_record_id,
        "on_demand_read_operation": runtime_execution.on_demand_read_operation.value,
        "snapshot_type": runtime_execution.snapshot_type.value,
        "on_demand_read_execution_outcome": runtime_execution.execution_outcome.value,
        "attempt_final_status": str(mapping["attempt_final_status"].value),
        "command_final_status": str(mapping["command_final_status"].value),
        "job_run_final_status": (
            str(mapping["job_run_final_status"].value)
            if mapping["job_run_final_status"] is not None
            else None
        ),
        "terminalization_reason_category": str(mapping["terminalization_reason_category"]),
        "terminalization_reason": payload.terminalization_reason,
        "terminalized_at": terminalized_at.isoformat(),
        "reused_existing_terminalization": False,
        "trace_references": {
            "session_identifier": runtime_execution.session_identifier,
            "correlation_id": runtime_execution.correlation_id,
            "request_id": runtime_execution.request_id,
        },
    }


def _apply_on_demand_read_terminal_state(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun | None,
    runtime_execution: RuntimeOnDemandReadExecutionResult,
    mapping: dict[str, object],
    result_summary: dict[str, object],
    terminalized_at: datetime,
) -> None:
    attempt.status = mapping["attempt_final_status"]
    attempt.ended_at = terminalized_at
    attempt.response_snapshot = runtime_execution.adapter_response_snapshot or attempt.response_snapshot
    if mapping["attempt_final_status"] == CommandExecutionAttemptStatus.SUCCEEDED:
        attempt.error_code = None
        attempt.error_message = None
    else:
        attempt.error_code = str(mapping["error_code"])
        attempt.error_message = str(mapping["error_message"])
    command.current_status = mapping["command_final_status"]
    command.completed_at = terminalized_at
    if command.started_at is None:
        command.started_at = terminalized_at
    if mapping["command_final_status"] == CommandStatus.SUCCEEDED:
        command.latest_error_code = None
        command.latest_error_message = None
    else:
        command.latest_error_code = str(mapping["error_code"])
        command.latest_error_message = str(mapping["error_message"])
    command.result_summary = result_summary
    if job_run is not None:
        job_run.status = mapping["job_run_final_status"]
        job_run.completed_at = terminalized_at
        job_run.claim_expires_at = None
        job_run.related_command_id = command.id
        job_run.result_summary = result_summary
        if mapping["job_run_final_status"] == JobRunStatus.SUCCEEDED:
            job_run.latest_error_code = None
            job_run.latest_error_message = None
        else:
            job_run.latest_error_code = str(mapping["error_code"])
            job_run.latest_error_message = str(mapping["error_message"])


def _build_terminalization_response(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    job_run: JobRun | None,
    terminalization_record: dict[str, object],
    reused_existing_terminalization: bool,
) -> OnDemandReadRuntimeTerminalizationResponse:
    return OnDemandReadRuntimeTerminalizationResponse(
        result=OnDemandReadRuntimeTerminalizationResult(
            terminalization_status=str(terminalization_record["terminalization_status"]),
            command_id=command.id,
            command_execution_attempt_id=attempt.id,
            job_run_id=job_run.id if job_run is not None else None,
            terminalization_identifier=str(terminalization_record["terminalization_identifier"]),
            executor_identifier=str(terminalization_record["executor_identifier"]),
            runtime_on_demand_read_execution_record_id=str(
                terminalization_record["runtime_on_demand_read_execution_record_id"]
            ),
            on_demand_read_operation=OnDemandReadCommandOperation(
                str(terminalization_record["on_demand_read_operation"])
            ),
            snapshot_type=SnapshotType(str(terminalization_record["snapshot_type"])),
            on_demand_read_execution_outcome=str(
                terminalization_record["on_demand_read_execution_outcome"]
            ),
            attempt_final_status=CommandExecutionAttemptStatus(
                str(terminalization_record["attempt_final_status"])
            ),
            command_final_status=CommandStatus(str(terminalization_record["command_final_status"])),
            job_run_final_status=(
                JobRunStatus(str(terminalization_record["job_run_final_status"]))
                if terminalization_record.get("job_run_final_status") is not None
                else None
            ),
            terminalization_reason_category=str(
                terminalization_record["terminalization_reason_category"]
            ),
            terminalized_at=datetime.fromisoformat(str(terminalization_record["terminalized_at"])),
            reused_existing_terminalization=reused_existing_terminalization,
            terminalization_record=terminalization_record,
        ),
        job_run=serialize_job_run(job_run).model_dump(mode="json") if job_run is not None else None,
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _load_on_demand_read_runtime_handoff(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("on_demand_read_runtime_handoff")
    return payload if isinstance(payload, dict) else None


def _load_on_demand_read_runtime_terminalization(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("on_demand_read_runtime_terminalization")
    return payload if isinstance(payload, dict) else None


def _load_runtime_on_demand_read_execution(
    execution_metadata: dict[str, object] | None,
) -> RuntimeOnDemandReadExecutionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_on_demand_read_execution")
    if not isinstance(payload, dict):
        return None
    return RuntimeOnDemandReadExecutionResult.model_validate(payload)
