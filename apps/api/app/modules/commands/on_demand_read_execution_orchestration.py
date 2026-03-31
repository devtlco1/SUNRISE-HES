from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import (
    CommandCategory,
    CommandStatus,
    OnDemandReadCommandOperation,
)
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.on_demand_read_runtime_handoff import (
    handoff_on_demand_read_command_to_runtime,
)
from app.modules.commands.on_demand_read_runtime_terminalization import (
    terminalize_on_demand_read_runtime_execution,
)
from app.modules.commands.schemas import (
    OnDemandReadAttemptBootstrapRequest,
    OnDemandReadExecutionOrchestrationRequest,
    OnDemandReadExecutionOrchestrationResponse,
    OnDemandReadExecutionOrchestrationResult,
    OnDemandReadRuntimeHandoffRequest,
    OnDemandReadRuntimeTerminalizationRequest,
)
from app.modules.commands.service import (
    _validate_on_demand_read_normalized_payload,
    bootstrap_on_demand_read_command_attempt,
    get_meter_command,
    serialize_command_attempt,
    serialize_meter_command,
)
from app.modules.jobs.models import JobRun
from app.modules.jobs.service import serialize_job_run
from app.modules.readings.enums import SnapshotType
from app.runtime.services.runtime_artifact_utils import merge_runtime_metadata


def orchestrate_on_demand_read_command_execution(
    session: Session,
    *,
    command_id: uuid.UUID,
    payload: OnDemandReadExecutionOrchestrationRequest,
) -> OnDemandReadExecutionOrchestrationResponse:
    command = get_meter_command(session, command_id)
    latest_attempt = _load_latest_on_demand_read_attempt(session, command_id=command.id)
    existing_orchestration = _load_on_demand_read_execution_orchestration(
        latest_attempt.execution_metadata if latest_attempt is not None else None
    )
    if existing_orchestration is not None:
        return _build_existing_orchestration_response(
            session,
            command=command,
            attempt=latest_attempt,
            payload=payload,
            orchestration_record=existing_orchestration,
        )

    if command.command_template.category != CommandCategory.ON_DEMAND_READ:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the on-demand-read execution orchestration slice.",
        )
    if latest_attempt is not None and latest_attempt.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read command already has an incompatible prior finalized execution without a matching orchestration artifact.",
        )
    if command.current_status in {
        CommandStatus.SUCCEEDED,
        CommandStatus.FAILED,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read command is not execution-eligible from its current state.",
        )
    normalized_payload = _validate_on_demand_read_normalized_payload(command)
    on_demand_read_operation = OnDemandReadCommandOperation(
        str(normalized_payload["on_demand_read_operation"])
    )
    snapshot_type = SnapshotType(str(normalized_payload["on_demand_read"]["snapshot_type"]))

    bootstrap_identifier = _build_on_demand_read_orchestration_bootstrap_identifier(
        payload.orchestration_identifier
    )
    bootstrap_on_demand_read_command_attempt(
        session,
        command_id=command.id,
        payload=OnDemandReadAttemptBootstrapRequest(
            bootstrap_identifier=bootstrap_identifier,
            bootstrap_reason=payload.orchestration_reason or "on-demand-read-execution-orchestration",
        ),
    )
    handoff_response = handoff_on_demand_read_command_to_runtime(
        session,
        command_id=command.id,
        payload=OnDemandReadRuntimeHandoffRequest(
            handoff_identifier=payload.orchestration_identifier,
            executor_identifier=payload.executor_identifier,
            handoff_reason=payload.orchestration_reason or "on-demand-read-execution-orchestration",
            lease_seconds=payload.lease_seconds,
            session_timeout_seconds=payload.session_timeout_seconds,
        ),
    )
    terminalization_response = terminalize_on_demand_read_runtime_execution(
        session,
        command_id=command.id,
        payload=OnDemandReadRuntimeTerminalizationRequest(
            terminalization_identifier=payload.orchestration_identifier,
            executor_identifier=payload.executor_identifier,
            terminalization_reason=payload.orchestration_reason
            or "on-demand-read-execution-orchestration",
        ),
    )

    attempt = session.get(
        CommandExecutionAttempt,
        terminalization_response.created_or_existing_attempt.id,
    )
    refreshed_command = session.get(MeterCommand, command.id)
    job_run = (
        session.get(JobRun, terminalization_response.created_or_existing_attempt.job_run_id)
        if terminalization_response.created_or_existing_attempt.job_run_id is not None
        else None
    )
    if attempt is None or refreshed_command is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read execution orchestration could not load durable execution state.",
        )
    orchestration_record = _build_on_demand_read_execution_orchestration_record(
        command=refreshed_command,
        attempt=attempt,
        payload=payload,
        runtime_on_demand_read_execution_record_id=(
            handoff_response.result.runtime_on_demand_read_execution_record_id or ""
        ),
        on_demand_read_operation=on_demand_read_operation,
        snapshot_type=snapshot_type,
        terminalization_artifact_present=(
            "on_demand_read_runtime_terminalization" in (attempt.execution_metadata or {})
        ),
        orchestrated_at=datetime.now(UTC),
        reused_existing_orchestration=False,
        orchestration_reason_category="executed",
    )
    _persist_on_demand_read_execution_orchestration_record(
        session,
        attempt=attempt,
        command=refreshed_command,
        job_run=job_run,
        orchestration_record=orchestration_record,
    )
    session.refresh(attempt)
    session.refresh(refreshed_command)
    if job_run is not None:
        session.refresh(job_run)
    return _build_orchestration_response(
        command=refreshed_command,
        attempt=attempt,
        job_run=job_run,
        orchestration_record=orchestration_record,
        reused_existing_orchestration=False,
    )


def _build_existing_orchestration_response(
    session: Session,
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
    payload: OnDemandReadExecutionOrchestrationRequest,
    orchestration_record: dict[str, object],
) -> OnDemandReadExecutionOrchestrationResponse:
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read execution orchestration artifact references a missing attempt.",
        )
    if orchestration_record.get("orchestration_identifier") != payload.orchestration_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read execution orchestration already exists for another orchestration identifier.",
        )
    if orchestration_record.get("executor_identifier") != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read execution orchestration is already owned by another executor.",
        )
    job_run = session.get(JobRun, attempt.job_run_id) if attempt.job_run_id is not None else None
    return _build_orchestration_response(
        command=command,
        attempt=attempt,
        job_run=job_run,
        orchestration_record=orchestration_record,
        reused_existing_orchestration=True,
    )


def _build_orchestration_response(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    job_run: JobRun | None,
    orchestration_record: dict[str, object],
    reused_existing_orchestration: bool,
) -> OnDemandReadExecutionOrchestrationResponse:
    return OnDemandReadExecutionOrchestrationResponse(
        result=OnDemandReadExecutionOrchestrationResult(
            orchestration_status=str(orchestration_record["orchestration_status"]),
            orchestration_identifier=str(orchestration_record["orchestration_identifier"]),
            executor_identifier=str(orchestration_record["executor_identifier"]),
            command_id=command.id,
            command_execution_attempt_id=attempt.id,
            job_run_id=job_run.id if job_run is not None else None,
            runtime_on_demand_read_execution_record_id=str(
                orchestration_record["runtime_on_demand_read_execution_record_id"]
            ),
            on_demand_read_operation=OnDemandReadCommandOperation(
                str(orchestration_record["on_demand_read_operation"])
            ),
            snapshot_type=SnapshotType(str(orchestration_record["snapshot_type"])),
            terminalization_artifact_present=bool(
                orchestration_record["terminalization_artifact_present"]
            ),
            reused_existing_orchestration=reused_existing_orchestration,
            orchestrated_at=datetime.fromisoformat(str(orchestration_record["orchestrated_at"])),
            orchestration_reason_category=(
                str(orchestration_record["orchestration_reason_category"])
                if orchestration_record.get("orchestration_reason_category") is not None
                else None
            ),
            orchestration_record=orchestration_record,
        ),
        job_run=serialize_job_run(job_run).model_dump(mode="json") if job_run is not None else None,
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _build_on_demand_read_execution_orchestration_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    payload: OnDemandReadExecutionOrchestrationRequest,
    runtime_on_demand_read_execution_record_id: str,
    on_demand_read_operation: OnDemandReadCommandOperation,
    snapshot_type: SnapshotType,
    terminalization_artifact_present: bool,
    orchestrated_at: datetime,
    reused_existing_orchestration: bool,
    orchestration_reason_category: str | None,
) -> dict[str, object]:
    return {
        "orchestration_status": "orchestrated",
        "orchestration_identifier": payload.orchestration_identifier,
        "executor_identifier": payload.executor_identifier,
        "command_id": str(command.id),
        "command_execution_attempt_id": str(attempt.id),
        "job_run_id": str(attempt.job_run_id) if attempt.job_run_id is not None else None,
        "runtime_on_demand_read_execution_record_id": runtime_on_demand_read_execution_record_id,
        "on_demand_read_operation": on_demand_read_operation.value,
        "snapshot_type": snapshot_type.value,
        "terminalization_artifact_present": terminalization_artifact_present,
        "reused_existing_orchestration": reused_existing_orchestration,
        "orchestrated_at": orchestrated_at.isoformat(),
        "orchestration_reason_category": orchestration_reason_category,
    }


def _persist_on_demand_read_execution_orchestration_record(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun | None,
    orchestration_record: dict[str, object],
) -> None:
    payload = {"on_demand_read_execution_orchestration": orchestration_record}
    attempt.execution_metadata = merge_runtime_metadata(attempt.execution_metadata, payload)
    command.result_summary = merge_runtime_metadata(command.result_summary, payload)
    if job_run is not None:
        job_run.result_summary = merge_runtime_metadata(job_run.result_summary, payload)
        session.add(job_run)
    session.add_all([attempt, command])
    session.commit()


def _build_on_demand_read_orchestration_bootstrap_identifier(
    orchestration_identifier: str,
) -> str:
    return f"on-demand-read-orchestrator:{orchestration_identifier}"


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


def _load_on_demand_read_execution_orchestration(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("on_demand_read_execution_orchestration")
    return payload if isinstance(payload, dict) else None
