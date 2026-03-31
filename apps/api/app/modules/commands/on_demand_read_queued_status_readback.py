from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandCategory
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.on_demand_read_status_readback import (
    _load_artifact,
    _load_latest_on_demand_read_attempt,
    _read_bool_from_artifact,
    _resolve_on_demand_read_execution_outcome,
    _resolve_on_demand_read_operation,
    _resolve_runtime_on_demand_read_execution_record_id,
    _resolve_snapshot_type,
)
from app.modules.commands.schemas import (
    OnDemandReadQueuedStatusResponse,
    OnDemandReadQueuedStatusResult,
)
from app.modules.commands.service import get_meter_command


def get_on_demand_read_queued_execution_status(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> OnDemandReadQueuedStatusResponse:
    command = get_meter_command(session, command_id)
    if command.command_template.category != CommandCategory.ON_DEMAND_READ:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the on-demand-read queued status slice.",
        )

    attempt = _load_latest_on_demand_read_attempt(session, command_id=command.id)
    status_record = _build_on_demand_read_queued_status_record(command=command, attempt=attempt)
    return OnDemandReadQueuedStatusResponse(
        result=OnDemandReadQueuedStatusResult(
            command_id=command.id,
            command_status=command.current_status,
            command_execution_attempt_id=attempt.id if attempt is not None else None,
            queue_enqueue_status=_read_optional_str(status_record, "queue_enqueue_status"),
            queue_message_id=_read_optional_str(status_record, "queue_message_id"),
            queue_consumption_status=_read_optional_str(status_record, "queue_consumption_status"),
            runtime_on_demand_read_execution_record_id=_read_optional_str(
                status_record,
                "runtime_on_demand_read_execution_record_id",
            ),
            on_demand_read_operation=_resolve_on_demand_read_operation(
                command=command,
                attempt=attempt,
            ),
            snapshot_type=_resolve_snapshot_type(command=command, attempt=attempt),
            worker_consumed=bool(status_record["worker_consumed"]),
            queued_execute_now_artifact_present=bool(
                status_record["queued_execute_now_artifact_present"]
            ),
            queue_enqueue_artifact_present=bool(status_record["queue_enqueue_artifact_present"]),
            queue_consumption_artifact_present=bool(
                status_record["queue_consumption_artifact_present"]
            ),
            orchestration_artifact_present=bool(status_record["orchestration_artifact_present"]),
            terminalization_artifact_present=bool(status_record["terminalization_artifact_present"]),
            final_execution_outcome=_read_optional_str(status_record, "final_execution_outcome"),
            reused_existing_queued_execute_now=_read_optional_bool(
                status_record,
                "reused_existing_queued_execute_now",
            ),
            reused_existing_enqueue=_read_optional_bool(
                status_record,
                "reused_existing_enqueue",
            ),
            queued_status_record=status_record,
        )
    )


def _build_on_demand_read_queued_status_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
) -> dict[str, object]:
    attempt_metadata = attempt.execution_metadata if attempt is not None else {}
    command_summary = command.result_summary or {}
    queued_execute_now = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="on_demand_read_queued_execute_now",
    )
    queue_enqueue = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="on_demand_read_queue_enqueue",
    )
    queue_consumption = _load_artifact(
        attempt_metadata,
        command_summary,
        artifact_key="on_demand_read_queue_consumption",
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
    on_demand_read_operation = _resolve_on_demand_read_operation(command=command, attempt=attempt)
    snapshot_type = _resolve_snapshot_type(command=command, attempt=attempt)
    return {
        "command_id": str(command.id),
        "command_status": command.current_status.value,
        "command_execution_attempt_id": str(attempt.id) if attempt is not None else None,
        "queue_enqueue_status": _read_str_from_artifact(queue_enqueue, "queue_status"),
        "queue_message_id": _read_str_from_artifact(queue_enqueue, "message_id"),
        "queue_consumption_status": _read_str_from_artifact(
            queue_consumption,
            "consume_status",
        ),
        "runtime_on_demand_read_execution_record_id": (
            _resolve_runtime_on_demand_read_execution_record_id(
                command=command,
                attempt=attempt,
            )
        ),
        "on_demand_read_operation": (
            on_demand_read_operation.value if on_demand_read_operation is not None else None
        ),
        "snapshot_type": (
            snapshot_type.value if snapshot_type is not None else None
        ),
        "worker_consumed": queue_consumption is not None,
        "queued_execute_now_artifact_present": queued_execute_now is not None,
        "queue_enqueue_artifact_present": queue_enqueue is not None,
        "queue_consumption_artifact_present": queue_consumption is not None,
        "orchestration_artifact_present": orchestration is not None,
        "terminalization_artifact_present": terminalization is not None,
        "final_execution_outcome": _resolve_on_demand_read_execution_outcome(
            command=command,
            attempt=attempt,
        ),
        "reused_existing_queued_execute_now": _read_bool_from_artifact(
            queued_execute_now,
            "reused_existing_queued_execute_now",
        ),
        "reused_existing_enqueue": _read_bool_from_artifact(
            queue_enqueue,
            "reused_existing_enqueue",
        ),
    }


def _read_str_from_artifact(
    artifact: dict[str, object] | None,
    field_name: str,
) -> str | None:
    if artifact is None:
        return None
    value = artifact.get(field_name)
    return value if isinstance(value, str) and value else None


def _read_optional_str(payload: dict[str, object], field_name: str) -> str | None:
    value = payload.get(field_name)
    return value if isinstance(value, str) and value else None


def _read_optional_bool(payload: dict[str, object], field_name: str) -> bool | None:
    value = payload.get(field_name)
    return value if isinstance(value, bool) else None
