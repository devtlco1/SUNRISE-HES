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
    RuntimeExecutionInvocationGateResult,
    RuntimeExecutionLeaseResult,
    RuntimeExecutionOutcomeResult,
    RuntimeExecutionOutcomeStatus,
    RuntimeExecutionSessionFinalizeResult,
    RuntimeExecutionSessionFinalizeStatus,
    RuntimeExecutionSessionLineage,
    RuntimeExecutionSessionResult,
    RuntimeExecutionSessionStatus,
)
from app.runtime.schemas import (
    RuntimeExecutionOutcomeCheckpointRequest,
    RuntimeExecutionOutcomeCheckpointResponse,
    RuntimeExecutionSessionFinalizeRequest,
    RuntimeExecutionSessionFinalizeResponse,
    RuntimeExecutionSessionHeartbeatRequest,
    RuntimeExecutionSessionResponse,
    RuntimeExecutionSessionStartRequest,
)

SESSION_ELIGIBLE_ATTEMPT_STATUSES = {CommandExecutionAttemptStatus.STARTED}


def start_runtime_execution_session(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionSessionStartRequest,
) -> RuntimeExecutionSessionResponse:
    attempt = _get_attempt_for_session(session, attempt_id=attempt_id)
    _ensure_attempt_is_session_eligible(attempt)
    job_run, command = _load_runtime_session_entities(session, attempt=attempt)
    lease, invocation, guard, prerequisite_expires_at = _validate_runtime_session_prerequisites(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )

    current_session = _load_runtime_execution_session(attempt.execution_metadata)
    if current_session is not None and _session_is_active(current_session):
        if current_session.executor_identifier == payload.executor_identifier:
            result = _bound_existing_runtime_execution_session_result(
                current_session=current_session,
                prerequisite_expires_at=prerequisite_expires_at,
            )
            if result.session_expires_at != current_session.session_expires_at:
                result = result.model_copy(update={"reused_existing_session": True})
                return _persist_runtime_execution_session(
                    session,
                    attempt=attempt,
                    job_run=job_run,
                    command=command,
                    result=result,
                )
            return RuntimeExecutionSessionResponse(
                result=result.model_copy(update={"reused_existing_session": True}),
                job_run=serialize_job_run(job_run),
                related_command=serialize_meter_command(command),
                created_or_existing_attempt=serialize_command_attempt(attempt),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is already owned by another executor.",
        )
    if (
        current_session is not None
        and current_session.status == RuntimeExecutionSessionStatus.FINALIZED
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is already finalized and cannot be restarted.",
        )

    result = _build_runtime_execution_session_result(
        attempt=attempt,
        payload=payload,
        lease=lease,
        invocation=invocation,
        guard=guard,
        prerequisite_expires_at=prerequisite_expires_at,
    )
    return _persist_runtime_execution_session(
        session,
        attempt=attempt,
        job_run=job_run,
        command=command,
        result=result,
    )


def heartbeat_runtime_execution_session(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionSessionHeartbeatRequest,
) -> RuntimeExecutionSessionResponse:
    attempt = _get_attempt_for_session(session, attempt_id=attempt_id)
    _ensure_attempt_is_session_eligible(attempt)
    job_run, command = _load_runtime_session_entities(session, attempt=attempt)
    _, _, guard, prerequisite_expires_at = _validate_runtime_session_prerequisites(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )

    current_session = _load_runtime_execution_session(attempt.execution_metadata)
    if current_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution heartbeat requires an active runtime session.",
        )
    if current_session.status == RuntimeExecutionSessionStatus.FINALIZED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is already finalized and cannot be heartbeated.",
        )
    if current_session.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution heartbeat does not match the active runtime session.",
        )
    if current_session.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if not _session_is_active(current_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is expired and cannot be heartbeated.",
        )

    refreshed_result = _refresh_runtime_execution_session_result(
        current_session=current_session,
        payload=payload,
        prerequisite_expires_at=prerequisite_expires_at,
    )
    return _persist_runtime_execution_session(
        session,
        attempt=attempt,
        job_run=job_run,
        command=command,
        result=refreshed_result,
    )


def finalize_runtime_execution_session(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionSessionFinalizeRequest,
) -> RuntimeExecutionSessionFinalizeResponse:
    attempt = _get_attempt_for_session(session, attempt_id=attempt_id)
    _ensure_attempt_is_session_eligible(attempt)
    job_run, command = _load_runtime_session_entities(session, attempt=attempt)

    current_session = _load_runtime_execution_session(attempt.execution_metadata)
    if current_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution finalize requires an active runtime session.",
        )
    if current_session.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution finalize does not match the active runtime session.",
        )
    if current_session.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if current_session.status == RuntimeExecutionSessionStatus.FINALIZED:
        return RuntimeExecutionSessionFinalizeResponse(
            result=_to_finalize_result(
                current_session=current_session,
                already_finalized=True,
            ),
            job_run=serialize_job_run(job_run),
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(attempt),
        )
    if not _session_is_active(current_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is expired and cannot be finalized.",
        )

    _validate_runtime_session_prerequisites(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )
    finalized_session = _build_finalized_runtime_execution_session_result(
        current_session=current_session,
        payload=payload,
    )
    _persist_runtime_execution_session_state(
        session,
        attempt=attempt,
        job_run=job_run,
        command=command,
        result=finalized_session,
    )
    return RuntimeExecutionSessionFinalizeResponse(
        result=_to_finalize_result(
            current_session=finalized_session,
            already_finalized=False,
        ),
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def record_runtime_execution_outcome(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionOutcomeCheckpointRequest,
) -> RuntimeExecutionOutcomeCheckpointResponse:
    attempt = _get_attempt_for_session(session, attempt_id=attempt_id)
    _ensure_attempt_is_session_eligible(attempt)
    job_run, command = _load_runtime_session_entities(session, attempt=attempt)

    current_session = _load_runtime_execution_session(attempt.execution_metadata)
    if current_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution outcome requires a finalized runtime session.",
        )
    if current_session.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution outcome does not match the finalized runtime session.",
        )
    if current_session.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if current_session.status != RuntimeExecutionSessionStatus.FINALIZED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution outcome requires a finalized runtime session.",
        )
    if current_session.finalized_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution finalized session is owned by another executor.",
        )

    _validate_runtime_execution_outcome_context(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )

    existing_outcome = _load_runtime_execution_outcome(attempt.execution_metadata)
    if existing_outcome is not None:
        if existing_outcome.session_identifier != payload.session_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime execution outcome is already recorded for another session.",
            )
        if existing_outcome.executor_identifier != payload.executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime execution outcome is already owned by another executor.",
            )
        return RuntimeExecutionOutcomeCheckpointResponse(
            result=existing_outcome.model_copy(update={"already_recorded": True}),
            job_run=serialize_job_run(job_run),
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(attempt),
        )

    outcome = _build_runtime_execution_outcome_result(
        attempt=attempt,
        current_session=current_session,
        payload=payload,
    )
    _persist_runtime_execution_outcome_state(
        session,
        attempt=attempt,
        job_run=job_run,
        command=command,
        result=outcome,
    )
    return RuntimeExecutionOutcomeCheckpointResponse(
        result=outcome,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _get_attempt_for_session(
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


def _ensure_attempt_is_session_eligible(attempt: CommandExecutionAttempt) -> None:
    if attempt.status not in SESSION_ELIGIBLE_ATTEMPT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Runtime execution session is not allowed from status "
                f"{attempt.status.value}."
            ),
        )


def _load_runtime_session_entities(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
) -> tuple:
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session requires an attempt linked to a job run.",
        )
    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )
    return job_run, command


def _validate_runtime_session_prerequisites(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
) -> tuple[
    RuntimeExecutionLeaseResult,
    RuntimeExecutionInvocationGateResult,
    dict[str, object],
    datetime,
]:
    lease = _load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session requires an active runtime lease.",
        )
    _ensure_lease_matches_executor(lease=lease, executor_identifier=executor_identifier)
    lease_expires_at = _parse_iso_timestamp(
        lease.lease_expires_at,
        invalid_detail="Runtime execution lease is invalid and cannot authorize session ownership.",
    )
    if lease_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is expired and cannot authorize session ownership.",
        )

    invocation = _load_runtime_execution_invocation(execution_metadata)
    if invocation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session requires an active runtime invocation gate.",
        )
    if invocation.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate is owned by another executor.",
        )
    gate_expires_at = _parse_iso_timestamp(
        invocation.gate_expires_at,
        invalid_detail="Runtime execution invocation gate is invalid and cannot authorize session ownership.",
    )
    if gate_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate is expired and cannot authorize session ownership.",
        )
    if invocation.lineage.lease_record_id != lease.lease_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate does not match the active runtime lease.",
        )

    guard = _load_runtime_execution_guard(execution_metadata)
    if guard is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session requires an active runtime execution guard.",
        )
    if guard.get("executor_identifier") != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard is owned by another executor.",
        )
    if guard.get("lease_record_id") != lease.lease_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard does not match the active runtime lease.",
        )
    if guard.get("invocation_record_id") != invocation.invocation_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard does not match the active runtime invocation gate.",
        )
    guard_expires_at = _parse_iso_timestamp(
        str(guard.get("guard_expires_at", "")),
        invalid_detail="Runtime execution guard is invalid and cannot authorize session ownership.",
    )
    if guard_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard is expired and cannot authorize session ownership.",
        )

    return lease, invocation, guard, min(lease_expires_at, gate_expires_at, guard_expires_at)


def _validate_runtime_execution_outcome_context(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
) -> None:
    lease = _load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution outcome requires a runtime lease.",
        )
    _ensure_lease_matches_executor(lease=lease, executor_identifier=executor_identifier)

    invocation = _load_runtime_execution_invocation(execution_metadata)
    if invocation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution outcome requires a runtime invocation gate.",
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
            detail="Runtime execution outcome requires a runtime execution guard.",
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


def _build_runtime_execution_session_result(
    *,
    attempt: CommandExecutionAttempt,
    payload: RuntimeExecutionSessionStartRequest,
    lease: RuntimeExecutionLeaseResult,
    invocation: RuntimeExecutionInvocationGateResult,
    guard: dict[str, object],
    prerequisite_expires_at: datetime,
) -> RuntimeExecutionSessionResult:
    now = datetime.now(UTC)
    session_started_at = now.isoformat()
    session_expires_at = _compute_session_expiry(
        now=now,
        session_timeout_seconds=payload.session_timeout_seconds,
        prerequisite_expires_at=prerequisite_expires_at,
    )
    return RuntimeExecutionSessionResult(
        status=RuntimeExecutionSessionStatus.ACTIVE,
        session_identifier=f"runtime-execution-session:{attempt.id}:{uuid.uuid4()}",
        executor_identifier=payload.executor_identifier,
        job_run_id=str(attempt.job_run_id),
        related_command_id=str(attempt.meter_command_id),
        command_attempt_id=str(attempt.id),
        session_started_at=session_started_at,
        last_heartbeat_at=session_started_at,
        session_expires_at=session_expires_at,
        reused_existing_session=False,
        heartbeat_refreshed=False,
        summary=(
            "Runtime execution session is active for placeholder in-flight ownership "
            "without starting protocol communication."
        ),
        lineage=RuntimeExecutionSessionLineage(
            handoff_record_id=invocation.lineage.handoff_record_id,
            lease_record_id=lease.lease_record_id,
            invocation_record_id=invocation.invocation_record_id,
            guard_record_id=str(guard.get("guard_record_id")),
            dispatch_request_identity=invocation.lineage.dispatch_request_identity,
            queue_message_id=invocation.lineage.queue_message_id,
            claim_token=invocation.lineage.claim_token,
            source_identifiers=invocation.lineage.source_identifiers,
            correlation_lineage=invocation.lineage.correlation_lineage,
            dispatch_metadata=invocation.lineage.dispatch_metadata,
            intended_worker_path=invocation.lineage.intended_worker_path,
        ),
    )


def _refresh_runtime_execution_session_result(
    *,
    current_session: RuntimeExecutionSessionResult,
    payload: RuntimeExecutionSessionHeartbeatRequest,
    prerequisite_expires_at: datetime,
) -> RuntimeExecutionSessionResult:
    now = datetime.now(UTC)
    return current_session.model_copy(
        update={
            "last_heartbeat_at": now.isoformat(),
            "session_expires_at": _compute_session_expiry(
                now=now,
                session_timeout_seconds=payload.session_timeout_seconds,
                prerequisite_expires_at=prerequisite_expires_at,
            ),
            "heartbeat_refreshed": True,
            "reused_existing_session": False,
        }
    )


def _build_runtime_execution_outcome_result(
    *,
    attempt: CommandExecutionAttempt,
    current_session: RuntimeExecutionSessionResult,
    payload: RuntimeExecutionOutcomeCheckpointRequest,
) -> RuntimeExecutionOutcomeResult:
    outcome_recorded_at = datetime.now(UTC).isoformat()
    return RuntimeExecutionOutcomeResult(
        status=RuntimeExecutionOutcomeStatus.RECORDED,
        outcome_record_id=(
            f"runtime-execution-outcome:{attempt.id}:{current_session.session_identifier}"
        ),
        session_identifier=current_session.session_identifier,
        executor_identifier=current_session.executor_identifier,
        job_run_id=str(attempt.job_run_id),
        related_command_id=str(attempt.meter_command_id),
        command_attempt_id=str(attempt.id),
        terminal_outcome=payload.terminal_outcome,
        outcome_recorded_at=outcome_recorded_at,
        outcome_recorded_by_executor_identifier=payload.executor_identifier,
        finalize_reason=current_session.finalize_reason,
        outcome_reason=payload.outcome_reason,
        summary_message=payload.summary_message,
        already_recorded=False,
        summary=(
            "Runtime execution outcome is durably checkpointed for the finalized "
            "placeholder session without protocol communication."
        ),
        lineage=current_session.lineage,
    )


def _build_finalized_runtime_execution_session_result(
    *,
    current_session: RuntimeExecutionSessionResult,
    payload: RuntimeExecutionSessionFinalizeRequest,
) -> RuntimeExecutionSessionResult:
    finalized_at = datetime.now(UTC).isoformat()
    return current_session.model_copy(
        update={
            "status": RuntimeExecutionSessionStatus.FINALIZED,
            "heartbeat_refreshed": False,
            "reused_existing_session": False,
            "finalized_at": finalized_at,
            "finalized_by_executor_identifier": payload.executor_identifier,
            "finalize_reason": payload.finalize_reason,
            "summary": (
                "Runtime execution session is durably finalized for placeholder "
                "ownership closure without protocol communication."
            ),
        }
    )


def _bound_existing_runtime_execution_session_result(
    *,
    current_session: RuntimeExecutionSessionResult,
    prerequisite_expires_at: datetime,
) -> RuntimeExecutionSessionResult:
    current_session_expires_at = _parse_iso_timestamp(
        current_session.session_expires_at,
        invalid_detail="Runtime execution session is invalid and cannot be reused.",
    )
    return current_session.model_copy(
        update={
            "session_expires_at": min(
                current_session_expires_at,
                prerequisite_expires_at,
            ).isoformat()
        }
    )


def _persist_runtime_execution_session(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    job_run,
    command,
    result: RuntimeExecutionSessionResult,
) -> RuntimeExecutionSessionResponse:
    _persist_runtime_execution_session_state(
        session,
        attempt=attempt,
        job_run=job_run,
        command=command,
        result=result,
    )
    return RuntimeExecutionSessionResponse(
        result=result,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _persist_runtime_execution_session_state(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    job_run,
    command,
    result: RuntimeExecutionSessionResult,
) -> None:
    session_metadata = {"runtime_execution_session": result.model_dump(mode="json")}
    attempt.execution_metadata = _merge_dicts(attempt.execution_metadata, session_metadata)
    command.result_summary = _merge_dicts(
        command.result_summary,
        {"runtime_execution_session": result.model_dump(mode="json")},
    )
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"runtime_execution_session": result.model_dump(mode="json")},
    )
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(job_run)


def _persist_runtime_execution_outcome_state(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    job_run,
    command,
    result: RuntimeExecutionOutcomeResult,
) -> None:
    outcome_metadata = {"runtime_execution_outcome": result.model_dump(mode="json")}
    attempt.execution_metadata = _merge_dicts(attempt.execution_metadata, outcome_metadata)
    command.result_summary = _merge_dicts(
        command.result_summary,
        {"runtime_execution_outcome": result.model_dump(mode="json")},
    )
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"runtime_execution_outcome": result.model_dump(mode="json")},
    )
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(job_run)


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


def _compute_session_expiry(
    *,
    now: datetime,
    session_timeout_seconds: int,
    prerequisite_expires_at: datetime,
) -> str:
    requested_expiry = now + timedelta(seconds=session_timeout_seconds)
    effective_expiry = min(requested_expiry, prerequisite_expires_at)
    if effective_expiry <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session prerequisites are expired and cannot authorize session ownership.",
        )
    return effective_expiry.isoformat()


def _session_is_active(session_result: RuntimeExecutionSessionResult) -> bool:
    if session_result.status != RuntimeExecutionSessionStatus.ACTIVE:
        return False
    try:
        session_expires_at = datetime.fromisoformat(session_result.session_expires_at)
    except ValueError:
        return False
    return session_expires_at > datetime.now(UTC)


def _parse_iso_timestamp(
    raw_value: str,
    *,
    invalid_detail: str,
) -> datetime:
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=invalid_detail,
        ) from exc


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


def _to_finalize_result(
    *,
    current_session: RuntimeExecutionSessionResult,
    already_finalized: bool,
) -> RuntimeExecutionSessionFinalizeResult:
    if current_session.finalized_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session finalize record is invalid.",
        )
    if current_session.finalized_by_executor_identifier is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session finalize owner is missing.",
        )
    return RuntimeExecutionSessionFinalizeResult(
        status=RuntimeExecutionSessionFinalizeStatus.FINALIZED,
        session_identifier=current_session.session_identifier,
        executor_identifier=current_session.executor_identifier,
        job_run_id=current_session.job_run_id,
        related_command_id=current_session.related_command_id,
        command_attempt_id=current_session.command_attempt_id,
        session_started_at=current_session.session_started_at,
        last_heartbeat_at=current_session.last_heartbeat_at,
        session_expires_at=current_session.session_expires_at,
        finalized_at=current_session.finalized_at,
        finalized_by_executor_identifier=current_session.finalized_by_executor_identifier,
        finalize_reason=current_session.finalize_reason,
        already_finalized=already_finalized,
        summary=current_session.summary,
        lineage=current_session.lineage,
    )
