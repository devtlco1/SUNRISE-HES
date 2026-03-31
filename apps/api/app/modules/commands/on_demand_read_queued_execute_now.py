from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import OnDemandReadCommandOperation
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.on_demand_read_queued_execution import (
    enqueue_on_demand_read_command_execution,
)
from app.modules.commands.schemas import (
    OnDemandReadQueuedExecuteNowRequest,
    OnDemandReadQueuedExecuteNowResponse,
    OnDemandReadQueuedExecuteNowResult,
    OnDemandReadQueuedExecutionEnqueueRequest,
)
from app.modules.commands.service import (
    serialize_command_attempt,
    serialize_meter_command,
    submit_on_demand_read_command,
)
from app.modules.readings.enums import SnapshotType
from app.runtime.services.runtime_artifact_utils import merge_runtime_metadata


def execute_on_demand_read_now_queued(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: OnDemandReadQueuedExecuteNowRequest,
    requested_by_user_id: uuid.UUID | None,
) -> OnDemandReadQueuedExecuteNowResponse:
    command = submit_on_demand_read_command(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=requested_by_user_id,
    )
    queued_execute_now_identifier = _build_queued_execute_now_identifier(command.id)
    latest_attempt = _load_latest_on_demand_read_attempt(session, command_id=command.id)
    existing_queued_execute_now = _load_on_demand_read_queued_execute_now(command.result_summary)
    if existing_queued_execute_now is not None:
        return _build_existing_queued_execute_now_response(
            command=command,
            attempt=latest_attempt,
            payload_identifier=queued_execute_now_identifier,
            queued_execute_now_record=existing_queued_execute_now,
        )

    enqueue_response = enqueue_on_demand_read_command_execution(
        session,
        command_id=command.id,
        payload=OnDemandReadQueuedExecutionEnqueueRequest(
            enqueue_identifier=queued_execute_now_identifier,
            enqueue_reason=payload.queued_execute_now_reason or "on-demand-read-queued-execute-now",
        ),
    )
    refreshed_command = session.get(MeterCommand, command.id)
    if refreshed_command is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read queued execute-now could not load durable queue state.",
        )
    latest_attempt = _load_latest_on_demand_read_attempt(session, command_id=refreshed_command.id)
    queued_execute_now_record = _build_on_demand_read_queued_execute_now_record(
        command=refreshed_command,
        attempt=latest_attempt,
        queued_execute_now_identifier=queued_execute_now_identifier,
        enqueue_response=enqueue_response,
        queued_at=enqueue_response.result.enqueued_at,
        reused_existing_queued_execute_now=False,
    )
    refreshed_command.result_summary = merge_runtime_metadata(
        refreshed_command.result_summary,
        {"on_demand_read_queued_execute_now": queued_execute_now_record},
    )
    session.add(refreshed_command)
    session.commit()
    session.refresh(refreshed_command)
    latest_attempt = _load_latest_on_demand_read_attempt(session, command_id=refreshed_command.id)
    return _build_queued_execute_now_response(
        command=refreshed_command,
        attempt=latest_attempt,
        queued_execute_now_record=queued_execute_now_record,
        reused_existing_queued_execute_now=False,
        reused_existing_enqueue=enqueue_response.result.reused_existing_enqueue,
    )


def _build_existing_queued_execute_now_response(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
    payload_identifier: str,
    queued_execute_now_record: dict[str, object],
) -> OnDemandReadQueuedExecuteNowResponse:
    if queued_execute_now_record.get("queued_execute_now_identifier") != payload_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read queued execute-now already exists for another execution context.",
        )
    return _build_queued_execute_now_response(
        command=command,
        attempt=attempt,
        queued_execute_now_record=queued_execute_now_record,
        reused_existing_queued_execute_now=True,
        reused_existing_enqueue=True,
    )


def _build_queued_execute_now_response(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
    queued_execute_now_record: dict[str, object],
    reused_existing_queued_execute_now: bool,
    reused_existing_enqueue: bool,
) -> OnDemandReadQueuedExecuteNowResponse:
    return OnDemandReadQueuedExecuteNowResponse(
        result=OnDemandReadQueuedExecuteNowResult(
            queued_execute_now_status=str(queued_execute_now_record["queued_execute_now_status"]),
            queued_execute_now_identifier=str(
                queued_execute_now_record["queued_execute_now_identifier"]
            ),
            command_id=command.id,
            command_status=command.current_status,
            command_execution_attempt_id=attempt.id if attempt is not None else None,
            queue_enqueue_status=str(queued_execute_now_record["queue_enqueue_status"]),
            queue_message_id=str(queued_execute_now_record["queue_message_id"]),
            on_demand_read_operation=OnDemandReadCommandOperation(
                str(queued_execute_now_record["on_demand_read_operation"])
            ),
            snapshot_type=SnapshotType(str(queued_execute_now_record["snapshot_type"])),
            reused_existing_queued_execute_now=reused_existing_queued_execute_now,
            reused_existing_enqueue=reused_existing_enqueue,
            queued_at=datetime.fromisoformat(str(queued_execute_now_record["queued_at"])),
            queued_execute_now_record=queued_execute_now_record,
        ),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt) if attempt is not None else None,
    )


def _build_on_demand_read_queued_execute_now_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt | None,
    queued_execute_now_identifier: str,
    enqueue_response,
    queued_at: datetime,
    reused_existing_queued_execute_now: bool,
) -> dict[str, object]:
    return {
        "queued_execute_now_status": "queued",
        "queued_execute_now_identifier": queued_execute_now_identifier,
        "command_id": str(command.id),
        "command_status": command.current_status.value,
        "command_execution_attempt_id": str(attempt.id) if attempt is not None else None,
        "queue_enqueue_status": enqueue_response.result.queue_status,
        "queue_message_id": enqueue_response.result.message_id,
        "queue_enqueue_artifact_present": True,
        "on_demand_read_operation": enqueue_response.result.on_demand_read_operation.value,
        "snapshot_type": enqueue_response.result.snapshot_type.value,
        "reused_existing_enqueue": enqueue_response.result.reused_existing_enqueue,
        "reused_existing_queued_execute_now": reused_existing_queued_execute_now,
        "queued_at": queued_at.isoformat(),
    }


def _build_queued_execute_now_identifier(command_id: uuid.UUID) -> str:
    return f"on-demand-read-queued-execute-now:{command_id}"


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


def _load_on_demand_read_queued_execute_now(
    result_summary: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(result_summary, dict):
        return None
    payload = result_summary.get("on_demand_read_queued_execute_now")
    return payload if isinstance(payload, dict) else None
