from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandCategory, RelayControlCommandOperation
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.schemas import (
    RelayControlExecutionStatusResponse,
    RelayControlExecutionStatusResult,
)
from app.modules.commands.service import get_meter_command


def get_relay_control_execution_status(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> RelayControlExecutionStatusResponse:
    command = get_meter_command(session, command_id)
    if command.command_template.category not in {
        CommandCategory.REMOTE_DISCONNECT,
        CommandCategory.REMOTE_RECONNECT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the relay-control execution status slice.",
        )

    attempt = _load_latest_relay_control_attempt(session, command_id=command.id)
    status_record = _build_relay_control_status_record(
        command=command,
        attempt=attempt,
    )
    relay_control_operation = _resolve_relay_control_operation(command=command, attempt=attempt)
    return RelayControlExecutionStatusResponse(
        result=RelayControlExecutionStatusResult(
            command_id=command.id,
            command_status=command.current_status,
            relay_control_operation=relay_control_operation,
            command_execution_attempt_id=attempt.id if attempt is not None else None,
            runtime_relay_control_execution_record_id=(
                _resolve_runtime_relay_control_execution_record_id(
                    command=command,
                    attempt=attempt,
                )
            ),
            relay_control_execution_outcome=_resolve_relay_control_execution_outcome(
                command=command,
                attempt=attempt,
            ),
            orchestration_artifact_present=bool(status_record["orchestration_artifact_present"]),
            terminalization_artifact_present=bool(
                status_record["terminalization_artifact_present"]
            ),
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


def _build_relay_control_status_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> dict[str, object]:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    execute_now = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="relay_control_execute_now",
    )
    orchestration = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="relay_control_execution_orchestration",
    )
    terminalization = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="relay_control_runtime_terminalization",
    )
    return {
        "command_id": str(command.id),
        "command_status": command.current_status.value,
        "relay_control_operation": (
            relay_control_operation.value
            if (
                relay_control_operation := _resolve_relay_control_operation(
                    command=command,
                    attempt=attempt,
                )
            )
            is not None
            else None
        ),
        "command_execution_attempt_id": str(attempt.id) if attempt is not None else None,
        "runtime_relay_control_execution_record_id": (
            _resolve_runtime_relay_control_execution_record_id(
                command=command,
                attempt=attempt,
            )
        ),
        "relay_control_execution_outcome": _resolve_relay_control_execution_outcome(
            command=command,
            attempt=attempt,
        ),
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


def _resolve_runtime_relay_control_execution_record_id(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> str | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_relay_control_execution", "relay_control_execution_record_id"),
        ("relay_control_execute_now", "runtime_relay_control_execution_record_id"),
        ("relay_control_execution_orchestration", "runtime_relay_control_execution_record_id"),
        ("relay_control_runtime_terminalization", "runtime_relay_control_execution_record_id"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _resolve_relay_control_execution_outcome(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> str | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_relay_control_execution", "execution_outcome"),
        ("relay_control_execute_now", "relay_control_execution_outcome"),
        ("relay_control_runtime_terminalization", "relay_control_execution_outcome"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _resolve_relay_control_operation(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> RelayControlCommandOperation | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_relay_control_execution", "relay_operation"),
        ("relay_control_execute_now", "relay_control_operation"),
        ("relay_control_execution_orchestration", "relay_control_operation"),
        ("relay_control_runtime_terminalization", "relay_control_operation"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return RelayControlCommandOperation(value)
    if isinstance(command.normalized_payload, dict):
        value = command.normalized_payload.get("relay_control_operation")
        if isinstance(value, str) and value:
            return RelayControlCommandOperation(value)
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
