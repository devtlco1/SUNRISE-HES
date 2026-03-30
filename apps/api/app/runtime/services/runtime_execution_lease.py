from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import serialize_command_attempt, serialize_meter_command
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.contracts import (
    RuntimeExecutionHandoffResult,
    RuntimeExecutionLeaseLineage,
    RuntimeExecutionLeaseResult,
    RuntimeExecutionLeaseStatus,
)
from app.runtime.schemas import RuntimeExecutionLeaseRequest, RuntimeExecutionLeaseResponse

LEASEABLE_ATTEMPT_STATUSES = {CommandExecutionAttemptStatus.STARTED}


def lease_runtime_execution_work_item(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionLeaseRequest,
) -> RuntimeExecutionLeaseResponse:
    attempt = _get_attempt_for_leasing(session, attempt_id=attempt_id)
    _ensure_attempt_is_leaseable(attempt)
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease requires an attempt linked to a job run.",
        )

    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )

    handoff = _load_runtime_handoff(job_run.result_summary)
    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution handoff is required before leasing runtime work.",
        )

    current_lease = _load_runtime_execution_lease(attempt.execution_metadata)
    now = datetime.now(UTC)
    if current_lease is not None and _lease_is_active(current_lease, now=now):
        if current_lease.executor_identifier == payload.executor_identifier:
            return RuntimeExecutionLeaseResponse(
                result=current_lease.model_copy(update={"reused_existing_lease": True}),
                job_run=serialize_job_run(job_run),
                related_command=serialize_meter_command(command),
                created_or_existing_attempt=serialize_command_attempt(attempt),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution work already has an active lease owned by another executor.",
        )

    leased_at = now.isoformat()
    lease_expires_at = (now + timedelta(seconds=payload.lease_seconds)).isoformat()
    result = _build_runtime_execution_lease_result(
        attempt=attempt,
        payload=payload,
        handoff=handoff,
        leased_at=leased_at,
        lease_expires_at=lease_expires_at,
    )
    lease_metadata = _build_runtime_execution_lease_metadata(result)
    attempt.execution_metadata = _merge_dicts(attempt.execution_metadata, lease_metadata)
    command.result_summary = _merge_dicts(
        command.result_summary,
        {"runtime_execution_lease": result.model_dump(mode="json")},
    )
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"runtime_execution_lease": result.model_dump(mode="json")},
    )
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(job_run)
    return RuntimeExecutionLeaseResponse(
        result=result,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _get_attempt_for_leasing(
    session: Session,
    *,
    attempt_id: uuid.UUID,
) -> CommandExecutionAttempt:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command execution attempt not found.",
        )
    if attempt.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Command execution attempt is already finalized.",
        )
    return attempt


def _ensure_attempt_is_leaseable(attempt: CommandExecutionAttempt) -> None:
    if attempt.status not in LEASEABLE_ATTEMPT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Runtime execution lease is not allowed from status {attempt.status.value}.",
        )


def _load_runtime_handoff(
    result_summary: dict[str, object] | None,
) -> RuntimeExecutionHandoffResult | None:
    if not isinstance(result_summary, dict):
        return None
    payload = result_summary.get("runtime_execution_handoff")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionHandoffResult.model_validate(payload)


def _load_runtime_execution_lease(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionLeaseResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_lease")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionLeaseResult.model_validate(payload)


def _lease_is_active(
    lease: RuntimeExecutionLeaseResult,
    *,
    now: datetime,
) -> bool:
    try:
        lease_expires_at = datetime.fromisoformat(lease.lease_expires_at)
    except ValueError:
        return False
    return lease_expires_at > now


def _build_runtime_execution_lease_result(
    *,
    attempt: CommandExecutionAttempt,
    payload: RuntimeExecutionLeaseRequest,
    handoff: RuntimeExecutionHandoffResult,
    leased_at: str,
    lease_expires_at: str,
) -> RuntimeExecutionLeaseResult:
    return RuntimeExecutionLeaseResult(
        status=RuntimeExecutionLeaseStatus.LEASED,
        lease_record_id=f"runtime-execution-lease:{attempt.id}:{payload.executor_identifier}",
        executor_identifier=payload.executor_identifier,
        job_run_id=str(attempt.job_run_id),
        related_command_id=str(attempt.meter_command_id),
        command_attempt_id=str(attempt.id),
        leased_at=leased_at,
        lease_expires_at=lease_expires_at,
        reused_existing_lease=False,
        summary=(
            "Runtime execution work is leased for executor coordination "
            "without invoking protocol execution."
        ),
        lineage=RuntimeExecutionLeaseLineage(
            handoff_record_id=handoff.handoff_record_id,
            dispatch_request_identity=handoff.lineage.dispatch_request_identity,
            queue_message_id=handoff.lineage.queue_message_id,
            claim_token=handoff.lineage.claim_token,
            source_identifiers=handoff.lineage.source_identifiers,
            correlation_lineage=handoff.lineage.correlation_lineage,
            dispatch_metadata=handoff.lineage.dispatch_metadata,
            intended_worker_path=handoff.lineage.intended_worker_path,
        ),
    )


def _build_runtime_execution_lease_metadata(
    result: RuntimeExecutionLeaseResult,
) -> dict[str, object]:
    return {"runtime_execution_lease": result.model_dump(mode="json")}


def _merge_dicts(
    existing: dict[str, object] | None,
    extra: dict[str, object] | None,
) -> dict[str, object]:
    merged: dict[str, object] = {}
    if isinstance(existing, dict):
        merged.update(existing)
    if isinstance(extra, dict):
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}  # type: ignore[index]
            else:
                merged[key] = value
    return merged
