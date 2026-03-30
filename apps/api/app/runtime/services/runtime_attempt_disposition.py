from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import (
    apply_command_status_transition,
    serialize_command_attempt,
    serialize_meter_command,
)
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.contracts import (
    RuntimeAttemptDispositionResult,
    RuntimeAttemptDispositionStatus,
    RuntimeExecutionInvocationGateResult,
    RuntimeExecutionLeaseResult,
    RuntimeExecutionOutcomeResult,
    RuntimeExecutionSessionResult,
    RuntimeExecutionSessionStatus,
)
from app.runtime.schemas import (
    RuntimeAttemptDispositionBridgeRequest,
    RuntimeAttemptDispositionBridgeResponse,
)

OUTCOME_TO_TERMINAL_STATE = {
    "completed": SimpleNamespace(
        attempt=CommandExecutionAttemptStatus.SUCCEEDED,
        command=CommandStatus.SUCCEEDED,
        job_run=JobRunStatus.SUCCEEDED,
    ),
    "succeeded": SimpleNamespace(
        attempt=CommandExecutionAttemptStatus.SUCCEEDED,
        command=CommandStatus.SUCCEEDED,
        job_run=JobRunStatus.SUCCEEDED,
    ),
    "failed": SimpleNamespace(
        attempt=CommandExecutionAttemptStatus.FAILED,
        command=CommandStatus.FAILED,
        job_run=JobRunStatus.FAILED,
    ),
    "timed_out": SimpleNamespace(
        attempt=CommandExecutionAttemptStatus.TIMED_OUT,
        command=CommandStatus.TIMED_OUT,
        job_run=JobRunStatus.TIMED_OUT,
    ),
    "timeout": SimpleNamespace(
        attempt=CommandExecutionAttemptStatus.TIMED_OUT,
        command=CommandStatus.TIMED_OUT,
        job_run=JobRunStatus.TIMED_OUT,
    ),
    "cancelled": SimpleNamespace(
        attempt=CommandExecutionAttemptStatus.CANCELLED,
        command=CommandStatus.CANCELLED,
        job_run=JobRunStatus.CANCELLED,
    ),
    "canceled": SimpleNamespace(
        attempt=CommandExecutionAttemptStatus.CANCELLED,
        command=CommandStatus.CANCELLED,
        job_run=JobRunStatus.CANCELLED,
    ),
}


def bridge_runtime_execution_outcome_to_attempt_disposition(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeAttemptDispositionBridgeRequest,
) -> RuntimeAttemptDispositionBridgeResponse:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command execution attempt not found.",
        )
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge requires an attempt linked to a job run.",
        )
    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )

    existing = _load_runtime_attempt_disposition(attempt.execution_metadata)
    if existing is not None:
        if existing.session_identifier != payload.session_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime attempt disposition is already recorded for another session.",
            )
        if existing.executor_identifier != payload.executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime attempt disposition is already owned by another executor.",
            )
        return RuntimeAttemptDispositionBridgeResponse(
            result=existing.model_copy(update={"already_recorded": True}),
            job_run=serialize_job_run(job_run),
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(attempt),
        )

    session_result = _load_runtime_execution_session(attempt.execution_metadata)
    if session_result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge requires a finalized runtime session.",
        )
    if session_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge does not match the finalized runtime session.",
        )
    if session_result.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if session_result.status != RuntimeExecutionSessionStatus.FINALIZED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge requires a finalized runtime session.",
        )
    if session_result.finalized_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution finalized session is owned by another executor.",
        )

    outcome = _load_runtime_execution_outcome(attempt.execution_metadata)
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge requires a recorded runtime execution outcome.",
        )
    if outcome.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge does not match the recorded runtime execution outcome.",
        )
    if outcome.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution outcome is owned by another executor.",
        )
    if outcome.outcome_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution outcome is owned by another executor.",
        )

    _validate_runtime_disposition_context(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )
    if attempt.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Command execution attempt is already finalized.",
        )

    disposition = _build_runtime_attempt_disposition_result(
        attempt=attempt,
        outcome=outcome,
        payload=payload,
    )
    _apply_runtime_attempt_terminal_state(
        attempt=attempt,
        command=command,
        job_run=job_run,
        disposition=disposition,
        payload=payload,
        outcome=outcome,
    )
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(command)
    session.refresh(job_run)
    return RuntimeAttemptDispositionBridgeResponse(
        result=disposition,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _build_runtime_attempt_disposition_result(
    *,
    attempt: CommandExecutionAttempt,
    outcome: RuntimeExecutionOutcomeResult,
    payload: RuntimeAttemptDispositionBridgeRequest,
) -> RuntimeAttemptDispositionResult:
    mapped = _map_terminal_outcome(outcome.terminal_outcome)
    disposition_recorded_at = datetime.now(UTC).isoformat()
    return RuntimeAttemptDispositionResult(
        status=RuntimeAttemptDispositionStatus.BRIDGED,
        disposition_record_id=(
            f"runtime-attempt-disposition:{attempt.id}:{outcome.outcome_record_id}"
        ),
        session_identifier=outcome.session_identifier,
        outcome_record_id=outcome.outcome_record_id,
        executor_identifier=payload.executor_identifier,
        job_run_id=str(attempt.job_run_id),
        related_command_id=str(attempt.meter_command_id),
        command_attempt_id=str(attempt.id),
        terminal_outcome=outcome.terminal_outcome,
        mapped_attempt_status=mapped.attempt.value,
        mapped_command_status=mapped.command.value,
        mapped_job_run_status=mapped.job_run.value,
        disposition_recorded_at=disposition_recorded_at,
        disposition_recorded_by_executor_identifier=payload.executor_identifier,
        disposition_reason=payload.disposition_reason,
        already_recorded=False,
        summary=(
            "Runtime execution outcome is bridged into a durable placeholder "
            "attempt terminal disposition without protocol communication."
        ),
        lineage=outcome.lineage,
    )


def _apply_runtime_attempt_terminal_state(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run,
    disposition: RuntimeAttemptDispositionResult,
    payload: RuntimeAttemptDispositionBridgeRequest,
    outcome: RuntimeExecutionOutcomeResult,
) -> None:
    now = datetime.now(UTC)
    mapped = _map_terminal_outcome(disposition.terminal_outcome)
    terminal_error_code = _build_terminal_error_code(mapped.attempt.value)
    terminal_error_message = (
        payload.disposition_reason
        or outcome.outcome_reason
        or outcome.summary_message
        or f"Placeholder runtime disposition mapped to {mapped.attempt.value}."
    )

    attempt.status = mapped.attempt
    attempt.ended_at = now
    if mapped.attempt == CommandExecutionAttemptStatus.SUCCEEDED:
        attempt.error_code = None
        attempt.error_message = None
    else:
        attempt.error_code = terminal_error_code
        attempt.error_message = terminal_error_message
    attempt.execution_metadata = _merge_dicts(
        attempt.execution_metadata,
        {"runtime_attempt_disposition": disposition.model_dump(mode="json")},
    )

    apply_command_status_transition(
        command,
        new_status=mapped.command,
        latest_error_message=None if mapped.command == CommandStatus.SUCCEEDED else terminal_error_message,
        latest_error_code=None if mapped.command == CommandStatus.SUCCEEDED else terminal_error_code,
        now=now,
    )
    command.result_summary = _merge_dicts(
        command.result_summary,
        {"runtime_attempt_disposition": disposition.model_dump(mode="json")},
    )

    job_run.status = mapped.job_run
    job_run.completed_at = now
    job_run.claim_expires_at = None
    job_run.related_command_id = command.id
    if mapped.job_run == JobRunStatus.SUCCEEDED:
        job_run.latest_error_code = None
        job_run.latest_error_message = None
    else:
        job_run.latest_error_code = terminal_error_code
        job_run.latest_error_message = terminal_error_message
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"runtime_attempt_disposition": disposition.model_dump(mode="json")},
    )


def _validate_runtime_disposition_context(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
) -> None:
    lease = _load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge requires a runtime lease.",
        )
    if lease.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is owned by another executor.",
        )

    invocation = _load_runtime_execution_invocation(execution_metadata)
    if invocation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge requires a runtime invocation gate.",
        )
    if invocation.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate is owned by another executor.",
        )
    if invocation.lineage.lease_record_id != lease.lease_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate does not match the runtime lease.",
        )

    guard = _load_runtime_execution_guard(execution_metadata)
    if guard is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition bridge requires a runtime execution guard.",
        )
    if guard.get("executor_identifier") != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard is owned by another executor.",
        )
    if guard.get("lease_record_id") != lease.lease_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard does not match the runtime lease.",
        )
    if guard.get("invocation_record_id") != invocation.invocation_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard does not match the runtime invocation gate.",
        )


def _load_runtime_execution_session(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionSessionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_session")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionSessionResult.model_validate(payload)


def _load_runtime_execution_outcome(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionOutcomeResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_outcome")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionOutcomeResult.model_validate(payload)


def _load_runtime_attempt_disposition(
    execution_metadata: dict[str, object] | None,
) -> RuntimeAttemptDispositionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_attempt_disposition")
    if not isinstance(payload, dict):
        return None
    return RuntimeAttemptDispositionResult.model_validate(payload)


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


def _load_runtime_execution_guard(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_guard")
    if not isinstance(payload, dict):
        return None
    return payload


def _map_terminal_outcome(terminal_outcome: str) -> SimpleNamespace:
    mapped = OUTCOME_TO_TERMINAL_STATE.get(terminal_outcome.strip().lower())
    if mapped is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runtime attempt disposition bridge does not support "
                f"terminal outcome '{terminal_outcome}'."
            ),
        )
    return mapped


def _build_terminal_error_code(mapped_attempt_status: str) -> str:
    return f"RUNTIME_{mapped_attempt_status.upper()}"


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
