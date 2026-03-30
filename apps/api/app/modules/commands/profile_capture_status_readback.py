from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandCategory
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.schemas import (
    ProfileCaptureExecutionStatusResponse,
    ProfileCaptureExecutionStatusResult,
)
from app.modules.commands.service import get_meter_command


def get_profile_capture_execution_status(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> ProfileCaptureExecutionStatusResponse:
    command = get_meter_command(session, command_id)
    if command.command_template.category != CommandCategory.PROFILE_CAPTURE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the profile-capture execution status slice.",
        )

    attempt = _load_latest_profile_capture_attempt(session, command_id=command.id)
    status_record = _build_profile_capture_status_record(
        command=command,
        attempt=attempt,
    )
    return ProfileCaptureExecutionStatusResponse(
        result=ProfileCaptureExecutionStatusResult(
            command_id=command.id,
            command_status=command.current_status,
            command_execution_attempt_id=attempt.id if attempt is not None else None,
            runtime_profile_read_execution_record_id=_resolve_runtime_profile_read_execution_record_id(
                command=command,
                attempt=attempt,
            ),
            terminal_status_category=_resolve_terminal_status_category(command=command, attempt=attempt),
            orchestration_artifact_present=bool(status_record["orchestration_artifact_present"]),
            terminalization_artifact_present=bool(status_record["terminalization_artifact_present"]),
            execute_now_artifact_present=bool(status_record["execute_now_artifact_present"]),
            reused_existing_execute_now=_read_optional_bool(
                status_record,
                "reused_existing_execute_now",
            ),
            reused_existing_orchestration=_read_optional_bool(
                status_record,
                "reused_existing_orchestration",
            ),
            reused_existing_terminalization=_read_optional_bool(
                status_record,
                "reused_existing_terminalization",
            ),
            status_record=status_record,
        )
    )


def _build_profile_capture_status_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> dict[str, object]:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    execute_now = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="profile_capture_execute_now",
    )
    orchestration = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="profile_capture_execution_orchestration",
    )
    terminalization = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="profile_capture_runtime_terminalization",
    )
    return {
        "command_id": str(command.id),
        "command_status": command.current_status.value,
        "command_execution_attempt_id": str(attempt.id) if attempt is not None else None,
        "runtime_profile_read_execution_record_id": _resolve_runtime_profile_read_execution_record_id(
            command=command,
            attempt=attempt,
        ),
        "terminal_status_category": _resolve_terminal_status_category(command=command, attempt=attempt),
        "orchestration_artifact_present": orchestration is not None,
        "terminalization_artifact_present": terminalization is not None,
        "execute_now_artifact_present": execute_now is not None,
        "reused_existing_execute_now": _read_bool_from_artifact(
            execute_now,
            "reused_existing_execute_now",
        ),
        "reused_existing_orchestration": _read_bool_from_artifact(
            orchestration,
            "reused_existing_orchestration",
        ),
        "reused_existing_terminalization": _read_bool_from_artifact(
            terminalization,
            "reused_existing_terminalization",
        ),
    }


def _resolve_runtime_profile_read_execution_record_id(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> str | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_profile_read_execution", "profile_read_execution_record_id"),
        ("profile_capture_execute_now", "runtime_profile_read_execution_record_id"),
        ("profile_capture_execution_orchestration", "runtime_profile_read_execution_record_id"),
        ("profile_capture_runtime_terminalization", "runtime_profile_read_execution_record_id"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _resolve_terminal_status_category(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> str | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_capture_load_profile_terminal_status", "terminal_status"),
        ("profile_capture_execute_now", "terminal_status_category"),
        ("profile_capture_runtime_terminalization", "runtime_capture_load_profile_terminal_status"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _load_artifact(
    attempt_metadata: dict[str, object] | None,
    command_summary: dict[str, object] | None,
    *,
    artifact_key: str,
) -> dict[str, object] | None:
    if isinstance(attempt_metadata, dict):
        attempt_payload = attempt_metadata.get(artifact_key)
        if isinstance(attempt_payload, dict):
            return attempt_payload
    if isinstance(command_summary, dict):
        command_payload = command_summary.get(artifact_key)
        if isinstance(command_payload, dict):
            return command_payload
    return None


def _read_bool_from_artifact(
    artifact: dict[str, object] | None,
    field_name: str,
) -> bool | None:
    if artifact is None:
        return None
    value = artifact.get(field_name)
    return value if isinstance(value, bool) else None


def _read_optional_bool(
    payload: dict[str, object],
    field_name: str,
) -> bool | None:
    value = payload.get(field_name)
    return value if isinstance(value, bool) else None


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
