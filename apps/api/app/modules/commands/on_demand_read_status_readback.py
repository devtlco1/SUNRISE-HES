from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandCategory, OnDemandReadCommandOperation
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.schemas import (
    OnDemandReadExecutionStatusResponse,
    OnDemandReadExecutionStatusResult,
)
from app.modules.commands.service import get_meter_command
from app.modules.readings.enums import SnapshotType


def get_on_demand_read_execution_status(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> OnDemandReadExecutionStatusResponse:
    command = get_meter_command(session, command_id)
    if command.command_template.category != CommandCategory.ON_DEMAND_READ:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the on-demand-read execution status slice.",
        )

    attempt = _load_latest_on_demand_read_attempt(session, command_id=command.id)
    status_record = _build_on_demand_read_status_record(
        command=command,
        attempt=attempt,
    )
    return OnDemandReadExecutionStatusResponse(
        result=OnDemandReadExecutionStatusResult(
            command_id=command.id,
            command_status=command.current_status,
            on_demand_read_operation=_resolve_on_demand_read_operation(
                command=command,
                attempt=attempt,
            ),
            snapshot_type=_resolve_snapshot_type(
                command=command,
                attempt=attempt,
            ),
            command_execution_attempt_id=attempt.id if attempt is not None else None,
            runtime_on_demand_read_execution_record_id=(
                _resolve_runtime_on_demand_read_execution_record_id(
                    command=command,
                    attempt=attempt,
                )
            ),
            on_demand_read_execution_outcome=_resolve_on_demand_read_execution_outcome(
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


def _build_on_demand_read_status_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> dict[str, object]:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    execute_now = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="on_demand_read_execute_now",
    )
    orchestration = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="on_demand_read_execution_orchestration",
    )
    terminalization = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="on_demand_read_runtime_terminalization",
    )
    on_demand_read_operation = _resolve_on_demand_read_operation(
        command=command,
        attempt=attempt,
    )
    snapshot_type = _resolve_snapshot_type(
        command=command,
        attempt=attempt,
    )
    return {
        "command_id": str(command.id),
        "command_status": command.current_status.value,
        "on_demand_read_operation": (
            on_demand_read_operation.value if on_demand_read_operation is not None else None
        ),
        "snapshot_type": snapshot_type.value if snapshot_type is not None else None,
        "command_execution_attempt_id": str(attempt.id) if attempt is not None else None,
        "runtime_on_demand_read_execution_record_id": (
            _resolve_runtime_on_demand_read_execution_record_id(
                command=command,
                attempt=attempt,
            )
        ),
        "on_demand_read_execution_outcome": _resolve_on_demand_read_execution_outcome(
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


def _resolve_runtime_on_demand_read_execution_record_id(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> str | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_on_demand_read_execution", "on_demand_read_execution_record_id"),
        ("on_demand_read_execute_now", "runtime_on_demand_read_execution_record_id"),
        ("on_demand_read_execution_orchestration", "runtime_on_demand_read_execution_record_id"),
        ("on_demand_read_runtime_terminalization", "runtime_on_demand_read_execution_record_id"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _resolve_on_demand_read_execution_outcome(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> str | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_on_demand_read_execution", "execution_outcome"),
        ("on_demand_read_execute_now", "on_demand_read_execution_outcome"),
        ("on_demand_read_runtime_terminalization", "on_demand_read_execution_outcome"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _resolve_on_demand_read_operation(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> OnDemandReadCommandOperation | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_on_demand_read_execution", "on_demand_read_operation"),
        ("on_demand_read_execute_now", "on_demand_read_operation"),
        ("on_demand_read_execution_orchestration", "on_demand_read_operation"),
        ("on_demand_read_runtime_terminalization", "on_demand_read_operation"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return OnDemandReadCommandOperation(value)
    if isinstance(command.normalized_payload, dict):
        value = command.normalized_payload.get("on_demand_read_operation")
        if isinstance(value, str) and value:
            return OnDemandReadCommandOperation(value)
    return None


def _resolve_snapshot_type(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> SnapshotType | None:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    for artifact_key, field_name in (
        ("runtime_on_demand_read_execution", "snapshot_type"),
        ("on_demand_read_execute_now", "snapshot_type"),
        ("on_demand_read_execution_orchestration", "snapshot_type"),
        ("on_demand_read_runtime_terminalization", "snapshot_type"),
    ):
        artifact = _load_artifact(attempt_metadata, command_summary, artifact_key=artifact_key)
        if artifact is None:
            continue
        value = artifact.get(field_name)
        if isinstance(value, str) and value:
            return SnapshotType(value)
    if isinstance(command.normalized_payload, dict):
        on_demand_read = command.normalized_payload.get("on_demand_read")
        if isinstance(on_demand_read, dict):
            value = on_demand_read.get("snapshot_type")
            if isinstance(value, str) and value:
                return SnapshotType(value)
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
