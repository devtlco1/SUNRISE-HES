from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import OnDemandReadCommandOperation
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.on_demand_read_execution_orchestration import (
    orchestrate_on_demand_read_command_execution,
)
from app.modules.commands.schemas import (
    OnDemandReadExecuteNowRequest,
    OnDemandReadExecuteNowResponse,
    OnDemandReadExecuteNowResult,
    OnDemandReadExecutionOrchestrationRequest,
    OnDemandReadExecutionOrchestrationResponse,
)
from app.modules.commands.service import (
    serialize_command_attempt,
    serialize_meter_command,
    submit_on_demand_read_command,
)
from app.modules.jobs.models import JobRun
from app.modules.readings.enums import SnapshotType
from app.runtime.services.runtime_artifact_utils import merge_runtime_metadata

ON_DEMAND_READ_EXECUTE_NOW_EXECUTOR = "on_demand_read_execute_now"


def execute_on_demand_read_now(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: OnDemandReadExecuteNowRequest,
    requested_by_user_id: uuid.UUID | None,
) -> OnDemandReadExecuteNowResponse:
    command = submit_on_demand_read_command(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=requested_by_user_id,
    )
    execute_now_identifier = _build_execute_now_identifier(command.id)
    latest_attempt = _load_latest_on_demand_read_attempt(session, command_id=command.id)
    existing_execute_now = _load_on_demand_read_execute_now(
        latest_attempt.execution_metadata if latest_attempt is not None else None
    )
    if existing_execute_now is not None:
        return _build_existing_execute_now_response(
            command=command,
            attempt=latest_attempt,
            payload_identifier=execute_now_identifier,
            execute_now_record=existing_execute_now,
        )

    orchestration = orchestrate_on_demand_read_command_execution(
        session,
        command_id=command.id,
        payload=OnDemandReadExecutionOrchestrationRequest(
            orchestration_identifier=execute_now_identifier,
            executor_identifier=ON_DEMAND_READ_EXECUTE_NOW_EXECUTOR,
            orchestration_reason=payload.execute_now_reason or "on-demand-read-execute-now",
        ),
    )
    attempt = session.get(CommandExecutionAttempt, orchestration.created_or_existing_attempt.id)
    refreshed_command = session.get(MeterCommand, command.id)
    job_run = (
        session.get(JobRun, attempt.job_run_id)
        if attempt is not None and attempt.job_run_id is not None
        else None
    )
    if attempt is None or refreshed_command is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read execute-now could not load durable execution state.",
        )
    runtime_on_demand_read_execution_record_id = (
        _resolve_runtime_on_demand_read_execution_record_id(
            attempt=attempt,
            orchestration_response=orchestration,
        )
    )
    on_demand_read_execution_outcome = _resolve_on_demand_read_execution_outcome(attempt)
    on_demand_read_operation = _resolve_on_demand_read_operation(
        attempt=attempt,
        command=refreshed_command,
    )
    snapshot_type = _resolve_snapshot_type(
        attempt=attempt,
        command=refreshed_command,
    )
    execute_now_record = _build_on_demand_read_execute_now_record(
        command=refreshed_command,
        attempt=attempt,
        execute_now_identifier=execute_now_identifier,
        runtime_on_demand_read_execution_record_id=runtime_on_demand_read_execution_record_id,
        on_demand_read_operation=on_demand_read_operation,
        snapshot_type=snapshot_type,
        on_demand_read_execution_outcome=on_demand_read_execution_outcome,
        executed_at=datetime.now(UTC),
        reused_existing_execute_now=False,
    )
    payload_record = {"on_demand_read_execute_now": execute_now_record}
    attempt.execution_metadata = merge_runtime_metadata(attempt.execution_metadata, payload_record)
    refreshed_command.result_summary = merge_runtime_metadata(
        refreshed_command.result_summary,
        payload_record,
    )
    if job_run is not None:
        job_run.result_summary = merge_runtime_metadata(job_run.result_summary, payload_record)
        session.add(job_run)
    session.add_all([attempt, refreshed_command])
    session.commit()
    session.refresh(attempt)
    session.refresh(refreshed_command)
    if job_run is not None:
        session.refresh(job_run)
    return _build_execute_now_response(
        command=refreshed_command,
        attempt=attempt,
        execute_now_record=execute_now_record,
        reused_existing_execute_now=False,
    )


def _build_existing_execute_now_response(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
    payload_identifier: str,
    execute_now_record: dict[str, object],
) -> OnDemandReadExecuteNowResponse:
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read execute-now artifact references a missing attempt.",
        )
    if execute_now_record.get("execute_now_identifier") != payload_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read execute-now already exists for another execution context.",
        )
    return _build_execute_now_response(
        command=command,
        attempt=attempt,
        execute_now_record=execute_now_record,
        reused_existing_execute_now=True,
    )


def _build_execute_now_response(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    execute_now_record: dict[str, object],
    reused_existing_execute_now: bool,
) -> OnDemandReadExecuteNowResponse:
    return OnDemandReadExecuteNowResponse(
        result=OnDemandReadExecuteNowResult(
            execute_now_status=str(execute_now_record["execute_now_status"]),
            execute_now_identifier=str(execute_now_record["execute_now_identifier"]),
            command_id=command.id,
            command_status=command.current_status,
            command_execution_attempt_id=attempt.id,
            runtime_on_demand_read_execution_record_id=str(
                execute_now_record["runtime_on_demand_read_execution_record_id"]
            ),
            on_demand_read_operation=OnDemandReadCommandOperation(
                str(execute_now_record["on_demand_read_operation"])
            ),
            snapshot_type=SnapshotType(str(execute_now_record["snapshot_type"])),
            on_demand_read_execution_outcome=(
                str(execute_now_record["on_demand_read_execution_outcome"])
                if execute_now_record.get("on_demand_read_execution_outcome") is not None
                else None
            ),
            orchestration_artifact_present=bool(
                execute_now_record["orchestration_artifact_present"]
            ),
            terminalization_artifact_present=bool(
                execute_now_record["terminalization_artifact_present"]
            ),
            reused_existing_execute_now=reused_existing_execute_now,
            executed_at=datetime.fromisoformat(str(execute_now_record["executed_at"])),
            execute_now_record=execute_now_record,
        ),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _build_on_demand_read_execute_now_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    execute_now_identifier: str,
    runtime_on_demand_read_execution_record_id: str,
    on_demand_read_operation: OnDemandReadCommandOperation,
    snapshot_type: SnapshotType,
    on_demand_read_execution_outcome: str | None,
    executed_at: datetime,
    reused_existing_execute_now: bool,
) -> dict[str, object]:
    execution_metadata = attempt.execution_metadata or {}
    return {
        "execute_now_status": "executed",
        "execute_now_identifier": execute_now_identifier,
        "command_id": str(command.id),
        "command_execution_attempt_id": str(attempt.id),
        "runtime_on_demand_read_execution_record_id": runtime_on_demand_read_execution_record_id,
        "on_demand_read_operation": on_demand_read_operation.value,
        "snapshot_type": snapshot_type.value,
        "on_demand_read_execution_outcome": on_demand_read_execution_outcome,
        "orchestration_artifact_present": "on_demand_read_execution_orchestration"
        in execution_metadata,
        "terminalization_artifact_present": "on_demand_read_runtime_terminalization"
        in execution_metadata,
        "reused_existing_execute_now": reused_existing_execute_now,
        "executed_at": executed_at.isoformat(),
    }


def _resolve_runtime_on_demand_read_execution_record_id(
    *,
    attempt: CommandExecutionAttempt,
    orchestration_response: OnDemandReadExecutionOrchestrationResponse,
) -> str:
    execution_metadata = attempt.execution_metadata or {}
    runtime_on_demand_read_execution = execution_metadata.get("runtime_on_demand_read_execution")
    if isinstance(runtime_on_demand_read_execution, dict):
        record_id = runtime_on_demand_read_execution.get("on_demand_read_execution_record_id")
        if isinstance(record_id, str) and record_id:
            return record_id
    return orchestration_response.result.runtime_on_demand_read_execution_record_id


def _resolve_on_demand_read_execution_outcome(
    attempt: CommandExecutionAttempt,
) -> str | None:
    execution_metadata = attempt.execution_metadata or {}
    runtime_on_demand_read_execution = execution_metadata.get("runtime_on_demand_read_execution")
    if isinstance(runtime_on_demand_read_execution, dict):
        outcome = runtime_on_demand_read_execution.get("execution_outcome")
        if isinstance(outcome, str) and outcome:
            return outcome
    terminalization = execution_metadata.get("on_demand_read_runtime_terminalization")
    if not isinstance(terminalization, dict):
        return None
    outcome = terminalization.get("on_demand_read_execution_outcome")
    return outcome if isinstance(outcome, str) else None


def _resolve_on_demand_read_operation(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
) -> OnDemandReadCommandOperation:
    execution_metadata = attempt.execution_metadata or {}
    runtime_on_demand_read_execution = execution_metadata.get("runtime_on_demand_read_execution")
    if isinstance(runtime_on_demand_read_execution, dict):
        operation = runtime_on_demand_read_execution.get("on_demand_read_operation")
        if isinstance(operation, str) and operation:
            return OnDemandReadCommandOperation(operation)
    if isinstance(command.normalized_payload, dict):
        operation = command.normalized_payload.get("on_demand_read_operation")
        if isinstance(operation, str) and operation:
            return OnDemandReadCommandOperation(operation)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="On-demand-read execute-now could not resolve the on-demand-read operation from durable state.",
    )


def _resolve_snapshot_type(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
) -> SnapshotType:
    execution_metadata = attempt.execution_metadata or {}
    runtime_on_demand_read_execution = execution_metadata.get("runtime_on_demand_read_execution")
    if isinstance(runtime_on_demand_read_execution, dict):
        snapshot_type = runtime_on_demand_read_execution.get("snapshot_type")
        if isinstance(snapshot_type, str) and snapshot_type:
            return SnapshotType(snapshot_type)
    if isinstance(command.normalized_payload, dict):
        on_demand_read = command.normalized_payload.get("on_demand_read")
        if isinstance(on_demand_read, dict):
            snapshot_type = on_demand_read.get("snapshot_type")
            if isinstance(snapshot_type, str) and snapshot_type:
                return SnapshotType(snapshot_type)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="On-demand-read execute-now could not resolve the snapshot type from durable state.",
    )


def _build_execute_now_identifier(command_id: uuid.UUID) -> str:
    return f"on-demand-read-execute-now:{command_id}"


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


def _load_on_demand_read_execute_now(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("on_demand_read_execute_now")
    return payload if isinstance(payload, dict) else None
