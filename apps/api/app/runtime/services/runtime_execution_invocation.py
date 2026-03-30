from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import serialize_command_attempt, serialize_meter_command
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.contracts import (
    RuntimeExecutionInvocationGateResult,
    RuntimeExecutionInvocationLineage,
    RuntimeExecutionInvocationStatus,
    RuntimeExecutionLeaseResult,
)
from app.runtime.schemas import (
    RuntimeExecutionInvocationGateRequest,
    RuntimeExecutionInvocationGateResponse,
)

INVOKABLE_ATTEMPT_STATUSES = {CommandExecutionAttemptStatus.STARTED}


def gate_runtime_execution_invocation(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionInvocationGateRequest,
) -> RuntimeExecutionInvocationGateResponse:
    attempt = _get_attempt_for_invocation(session, attempt_id=attempt_id)
    _ensure_attempt_is_invocable(attempt)
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation requires an attempt linked to a job run.",
        )

    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )

    lease = _load_runtime_execution_lease(attempt.execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation requires an active runtime lease.",
        )
    _ensure_lease_matches_executor(lease=lease, executor_identifier=payload.executor_identifier)
    _ensure_lease_is_active(lease)

    current_invocation = _load_runtime_execution_invocation(attempt.execution_metadata)
    if current_invocation is not None and _invocation_is_active(current_invocation):
        if current_invocation.executor_identifier == payload.executor_identifier:
            return RuntimeExecutionInvocationGateResponse(
                result=current_invocation.model_copy(update={"reused_existing_invocation": True}),
                job_run=serialize_job_run(job_run),
                related_command=serialize_meter_command(command),
                created_or_existing_attempt=serialize_command_attempt(attempt),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation is already authorized for another executor.",
        )

    invoked_at = datetime.now(UTC).isoformat()
    result = _build_runtime_execution_invocation_result(
        attempt=attempt,
        payload=payload,
        lease=lease,
        invoked_at=invoked_at,
    )
    invocation_metadata = {"runtime_execution_invocation_gate": result.model_dump(mode="json")}
    attempt.execution_metadata = _merge_dicts(attempt.execution_metadata, invocation_metadata)
    command.result_summary = _merge_dicts(
        command.result_summary,
        {"runtime_execution_invocation_gate": result.model_dump(mode="json")},
    )
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"runtime_execution_invocation_gate": result.model_dump(mode="json")},
    )
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(job_run)
    return RuntimeExecutionInvocationGateResponse(
        result=result,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _get_attempt_for_invocation(
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


def _ensure_attempt_is_invocable(attempt: CommandExecutionAttempt) -> None:
    if attempt.status not in INVOKABLE_ATTEMPT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runtime execution invocation gate is not allowed from status "
                f"{attempt.status.value}."
            ),
        )


def _load_runtime_execution_lease(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionLeaseResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_lease")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionLeaseResult.model_validate(payload)


def _load_runtime_execution_invocation(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionInvocationGateResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_invocation_gate")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionInvocationGateResult.model_validate(payload)


def _ensure_lease_matches_executor(
    *,
    lease: RuntimeExecutionLeaseResult,
    executor_identifier: str,
) -> None:
    if lease.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is owned by another executor.",
        )


def _ensure_lease_is_active(lease: RuntimeExecutionLeaseResult) -> None:
    try:
        lease_expires_at = datetime.fromisoformat(lease.lease_expires_at)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is invalid and cannot authorize invocation.",
        ) from exc
    if lease_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is expired and cannot authorize invocation.",
        )


def _build_runtime_execution_invocation_result(
    *,
    attempt: CommandExecutionAttempt,
    payload: RuntimeExecutionInvocationGateRequest,
    lease: RuntimeExecutionLeaseResult,
    invoked_at: str,
) -> RuntimeExecutionInvocationGateResult:
    return RuntimeExecutionInvocationGateResult(
        status=RuntimeExecutionInvocationStatus.AUTHORIZED,
        invocation_record_id=(
            f"runtime-execution-invocation:{attempt.id}:{payload.executor_identifier}"
        ),
        executor_identifier=payload.executor_identifier,
        job_run_id=str(attempt.job_run_id),
        related_command_id=str(attempt.meter_command_id),
        command_attempt_id=str(attempt.id),
        invoked_at=invoked_at,
        gate_expires_at=lease.lease_expires_at,
        reused_existing_invocation=False,
        summary=(
            "Runtime execution invocation is authorized by an active executor lease "
            "without starting protocol execution."
        ),
        lineage=RuntimeExecutionInvocationLineage(
            handoff_record_id=lease.lineage.handoff_record_id,
            lease_record_id=lease.lease_record_id,
            dispatch_request_identity=lease.lineage.dispatch_request_identity,
            queue_message_id=lease.lineage.queue_message_id,
            claim_token=lease.lineage.claim_token,
            source_identifiers=lease.lineage.source_identifiers,
            correlation_lineage=lease.lineage.correlation_lineage,
            dispatch_metadata=lease.lineage.dispatch_metadata,
            intended_worker_path=lease.lineage.intended_worker_path,
        ),
    )


def _invocation_is_active(invocation: RuntimeExecutionInvocationGateResult) -> bool:
    try:
        gate_expires_at = datetime.fromisoformat(invocation.gate_expires_at)
    except ValueError:
        return False
    return gate_expires_at > datetime.now(UTC)


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
