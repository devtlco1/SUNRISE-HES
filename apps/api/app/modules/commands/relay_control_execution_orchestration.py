from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import (
    CommandCategory,
    CommandStatus,
    RelayControlCommandOperation,
)
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.relay_control_runtime_handoff import (
    handoff_relay_control_command_to_runtime,
)
from app.modules.commands.relay_control_runtime_terminalization import (
    terminalize_relay_control_runtime_execution,
)
from app.modules.commands.schemas import (
    RelayControlAttemptBootstrapRequest,
    RelayControlExecutionOrchestrationRequest,
    RelayControlExecutionOrchestrationResponse,
    RelayControlExecutionOrchestrationResult,
    RelayControlRuntimeHandoffRequest,
    RelayControlRuntimeTerminalizationRequest,
)
from app.modules.commands.service import (
    _validate_relay_control_normalized_payload,
    bootstrap_relay_control_command_attempt,
    get_meter_command,
    serialize_command_attempt,
    serialize_meter_command,
)
from app.modules.jobs.models import JobRun
from app.modules.jobs.service import serialize_job_run
from app.runtime.services.runtime_artifact_utils import merge_runtime_metadata


def orchestrate_relay_control_command_execution(
    session: Session,
    *,
    command_id: uuid.UUID,
    payload: RelayControlExecutionOrchestrationRequest,
) -> RelayControlExecutionOrchestrationResponse:
    command = get_meter_command(session, command_id)
    latest_attempt = _load_latest_relay_control_attempt(session, command_id=command.id)
    existing_orchestration = _load_relay_control_execution_orchestration(
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

    if command.command_template.category not in {
        CommandCategory.REMOTE_DISCONNECT,
        CommandCategory.REMOTE_RECONNECT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the relay-control execution orchestration slice.",
        )
    if latest_attempt is not None and latest_attempt.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relay-control command already has an incompatible prior finalized execution without a matching orchestration artifact.",
        )
    if command.current_status in {
        CommandStatus.SUCCEEDED,
        CommandStatus.FAILED,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relay-control command is not execution-eligible from its current state.",
        )
    normalized_payload = _validate_relay_control_normalized_payload(command)
    relay_operation = RelayControlCommandOperation(
        str(normalized_payload["relay_control_operation"])
    )

    bootstrap_identifier = _build_relay_control_orchestration_bootstrap_identifier(
        payload.orchestration_identifier
    )
    bootstrap_relay_control_command_attempt(
        session,
        command_id=command.id,
        payload=RelayControlAttemptBootstrapRequest(
            bootstrap_identifier=bootstrap_identifier,
            bootstrap_reason=payload.orchestration_reason
            or "relay-control-execution-orchestration",
        ),
    )
    handoff_response = handoff_relay_control_command_to_runtime(
        session,
        command_id=command.id,
        payload=RelayControlRuntimeHandoffRequest(
            handoff_identifier=payload.orchestration_identifier,
            executor_identifier=payload.executor_identifier,
            handoff_reason=payload.orchestration_reason
            or "relay-control-execution-orchestration",
            lease_seconds=payload.lease_seconds,
            session_timeout_seconds=payload.session_timeout_seconds,
        ),
    )
    terminalization_response = terminalize_relay_control_runtime_execution(
        session,
        command_id=command.id,
        payload=RelayControlRuntimeTerminalizationRequest(
            terminalization_identifier=payload.orchestration_identifier,
            executor_identifier=payload.executor_identifier,
            terminalization_reason=payload.orchestration_reason
            or "relay-control-execution-orchestration",
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
            detail="Relay-control execution orchestration could not load durable execution state.",
        )
    orchestration_record = _build_relay_control_execution_orchestration_record(
        command=refreshed_command,
        attempt=attempt,
        payload=payload,
        runtime_relay_control_execution_record_id=(
            handoff_response.result.runtime_relay_control_execution_record_id
        ),
        terminalization_artifact_present=(
            "relay_control_runtime_terminalization" in (attempt.execution_metadata or {})
        ),
        relay_control_operation=relay_operation,
        orchestrated_at=datetime.now(UTC),
        reused_existing_orchestration=False,
        orchestration_reason_category="executed",
    )
    _persist_relay_control_execution_orchestration_record(
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
    payload: RelayControlExecutionOrchestrationRequest,
    orchestration_record: dict[str, object],
) -> RelayControlExecutionOrchestrationResponse:
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relay-control execution orchestration artifact references a missing attempt.",
        )
    if orchestration_record.get("orchestration_identifier") != payload.orchestration_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relay-control execution orchestration already exists for another orchestration identifier.",
        )
    if orchestration_record.get("executor_identifier") != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relay-control execution orchestration is already owned by another executor.",
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
) -> RelayControlExecutionOrchestrationResponse:
    return RelayControlExecutionOrchestrationResponse(
        result=RelayControlExecutionOrchestrationResult(
            orchestration_status=str(orchestration_record["orchestration_status"]),
            orchestration_identifier=str(orchestration_record["orchestration_identifier"]),
            executor_identifier=str(orchestration_record["executor_identifier"]),
            command_id=command.id,
            command_execution_attempt_id=attempt.id,
            job_run_id=job_run.id if job_run is not None else None,
            runtime_relay_control_execution_record_id=str(
                orchestration_record["runtime_relay_control_execution_record_id"]
            ),
            relay_control_operation=RelayControlCommandOperation(
                str(orchestration_record["relay_control_operation"])
            ),
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


def _build_relay_control_execution_orchestration_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    payload: RelayControlExecutionOrchestrationRequest,
    runtime_relay_control_execution_record_id: str,
    terminalization_artifact_present: bool,
    relay_control_operation: RelayControlCommandOperation,
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
        "runtime_relay_control_execution_record_id": runtime_relay_control_execution_record_id,
        "relay_control_operation": relay_control_operation.value,
        "terminalization_artifact_present": terminalization_artifact_present,
        "reused_existing_orchestration": reused_existing_orchestration,
        "orchestrated_at": orchestrated_at.isoformat(),
        "orchestration_reason_category": orchestration_reason_category,
    }


def _persist_relay_control_execution_orchestration_record(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun | None,
    orchestration_record: dict[str, object],
) -> None:
    payload = {"relay_control_execution_orchestration": orchestration_record}
    attempt.execution_metadata = merge_runtime_metadata(attempt.execution_metadata, payload)
    command.result_summary = merge_runtime_metadata(command.result_summary, payload)
    if job_run is not None:
        job_run.result_summary = merge_runtime_metadata(job_run.result_summary, payload)
        session.add(job_run)
    session.add_all([attempt, command])
    session.commit()


def _build_relay_control_orchestration_bootstrap_identifier(
    orchestration_identifier: str,
) -> str:
    return f"relay-control-orchestrator:{orchestration_identifier}"


def _load_latest_relay_control_attempt(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandExecutionAttempt | None:
    return session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command_id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )


def _load_relay_control_execution_orchestration(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("relay_control_execution_orchestration")
    return payload if isinstance(payload, dict) else None
