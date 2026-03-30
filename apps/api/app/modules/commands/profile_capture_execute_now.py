from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.profile_capture_execution_orchestration import (
    orchestrate_profile_capture_command_execution,
)
from app.modules.commands.schemas import (
    ProfileCaptureExecuteNowRequest,
    ProfileCaptureExecuteNowResponse,
    ProfileCaptureExecuteNowResult,
    ProfileCaptureExecutionOrchestrationRequest,
    ProfileCaptureExecutionOrchestrationResponse,
)
from app.modules.commands.service import (
    serialize_command_attempt,
    serialize_meter_command,
    submit_capture_load_profile_command,
)
from app.modules.jobs.models import JobRun
from app.runtime.services.runtime_artifact_utils import merge_runtime_metadata

PROFILE_CAPTURE_EXECUTE_NOW_EXECUTOR = "profile_capture_execute_now"


def execute_profile_capture_now(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: ProfileCaptureExecuteNowRequest,
    requested_by_user_id: uuid.UUID | None,
) -> ProfileCaptureExecuteNowResponse:
    command = submit_capture_load_profile_command(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=requested_by_user_id,
    )
    execute_now_identifier = _build_execute_now_identifier(command.id)
    latest_attempt = _load_latest_profile_capture_attempt(session, command_id=command.id)
    existing_execute_now = _load_profile_capture_execute_now(
        latest_attempt.execution_metadata if latest_attempt is not None else None
    )
    if existing_execute_now is not None:
        return _build_existing_execute_now_response(
            command=command,
            attempt=latest_attempt,
            payload_identifier=execute_now_identifier,
            execute_now_record=existing_execute_now,
        )

    orchestration = orchestrate_profile_capture_command_execution(
        session,
        command_id=command.id,
        payload=ProfileCaptureExecutionOrchestrationRequest(
            orchestration_identifier=execute_now_identifier,
            executor_identifier=PROFILE_CAPTURE_EXECUTE_NOW_EXECUTOR,
            orchestration_reason=payload.execute_now_reason or "profile-capture-execute-now",
        ),
    )
    attempt = session.get(CommandExecutionAttempt, orchestration.created_or_existing_attempt.id)
    refreshed_command = session.get(MeterCommand, command.id)
    job_run = session.get(JobRun, attempt.job_run_id) if attempt is not None and attempt.job_run_id else None
    if attempt is None or refreshed_command is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture execute-now could not load durable execution state.",
        )
    runtime_profile_read_execution_record_id = _resolve_runtime_profile_read_execution_record_id(
        attempt=attempt,
        orchestration_response=orchestration,
    )
    terminal_status_category = _resolve_terminal_status_category(attempt)
    execute_now_record = _build_profile_capture_execute_now_record(
        command=refreshed_command,
        attempt=attempt,
        execute_now_identifier=execute_now_identifier,
        runtime_profile_read_execution_record_id=runtime_profile_read_execution_record_id,
        terminal_status_category=terminal_status_category,
        orchestrated_at=datetime.now(UTC),
        reused_existing_execute_now=False,
    )
    payload_record = {"profile_capture_execute_now": execute_now_record}
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
) -> ProfileCaptureExecuteNowResponse:
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture execute-now artifact references a missing attempt.",
        )
    if execute_now_record.get("execute_now_identifier") != payload_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture execute-now already exists for another execution context.",
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
) -> ProfileCaptureExecuteNowResponse:
    return ProfileCaptureExecuteNowResponse(
        result=ProfileCaptureExecuteNowResult(
            execute_now_status=str(execute_now_record["execute_now_status"]),
            execute_now_identifier=str(execute_now_record["execute_now_identifier"]),
            command_id=command.id,
            command_status=command.current_status,
            command_execution_attempt_id=attempt.id,
            runtime_profile_read_execution_record_id=str(
                execute_now_record["runtime_profile_read_execution_record_id"]
            ),
            terminal_status_category=(
                str(execute_now_record["terminal_status_category"])
                if execute_now_record.get("terminal_status_category") is not None
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


def _build_profile_capture_execute_now_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    execute_now_identifier: str,
    runtime_profile_read_execution_record_id: str,
    terminal_status_category: str | None,
    orchestrated_at: datetime,
    reused_existing_execute_now: bool,
) -> dict[str, object]:
    execution_metadata = attempt.execution_metadata or {}
    return {
        "execute_now_status": "executed",
        "execute_now_identifier": execute_now_identifier,
        "command_id": str(command.id),
        "command_execution_attempt_id": str(attempt.id),
        "runtime_profile_read_execution_record_id": runtime_profile_read_execution_record_id,
        "terminal_status_category": terminal_status_category,
        "orchestration_artifact_present": "profile_capture_execution_orchestration"
        in execution_metadata,
        "terminalization_artifact_present": "profile_capture_runtime_terminalization"
        in execution_metadata,
        "reused_existing_execute_now": reused_existing_execute_now,
        "executed_at": orchestrated_at.isoformat(),
    }


def _resolve_runtime_profile_read_execution_record_id(
    *,
    attempt: CommandExecutionAttempt,
    orchestration_response: ProfileCaptureExecutionOrchestrationResponse,
) -> str:
    execution_metadata = attempt.execution_metadata or {}
    runtime_profile_read_execution = execution_metadata.get("runtime_profile_read_execution")
    if isinstance(runtime_profile_read_execution, dict):
        record_id = runtime_profile_read_execution.get("profile_read_execution_record_id")
        if isinstance(record_id, str) and record_id:
            return record_id
    return orchestration_response.result.runtime_profile_read_execution_record_id


def _resolve_terminal_status_category(attempt: CommandExecutionAttempt) -> str | None:
    execution_metadata = attempt.execution_metadata or {}
    terminal_status = execution_metadata.get("runtime_capture_load_profile_terminal_status")
    if not isinstance(terminal_status, dict):
        return None
    category = terminal_status.get("terminal_status")
    return category if isinstance(category, str) else None


def _build_execute_now_identifier(command_id: uuid.UUID) -> str:
    return f"profile-capture-execute-now:{command_id}"


def _load_latest_profile_capture_attempt(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandExecutionAttempt | None:
    return session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command_id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )


def _load_profile_capture_execute_now(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("profile_capture_execute_now")
    return payload if isinstance(payload, dict) else None
