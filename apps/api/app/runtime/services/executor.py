from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import serialize_command_attempt
from app.modules.connectivity.enums import ConnectivitySessionStatus
from app.modules.connectivity.models import ConnectivitySessionHistory
from app.modules.connectivity.service import serialize_connectivity_session
from app.modules.jobs.models import JobRun
from app.modules.jobs.schemas import (
    CommandAttemptFailRequest,
    CommandAttemptSucceedRequest,
    CommandAttemptTimeoutRequest,
)
from app.modules.jobs.service import (
    fail_command_attempt,
    succeed_command_attempt,
    timeout_command_attempt,
)
from app.runtime.adapters import get_runtime_adapter
from app.runtime.contracts import (
    ProtocolExecutionPlan,
    RuntimeCommandOutcome,
    RuntimeCommandResult,
    RuntimeSessionResult,
)
from app.runtime.normalization import to_command_result_summary
from app.runtime.schemas import ExecuteRuntimePlanResponse
from app.runtime.services.downstream import consume_downstream_signals
from app.runtime.services.ingestion import persist_runtime_result_telemetry
from app.runtime.services.postprocessing import post_process_runtime_outcome
from app.runtime.services.runtime_execution_guard import (
    build_runtime_execution_guard_metadata,
)
from app.runtime.services.runtime_plan_builder import build_runtime_plan_for_command

EXECUTABLE_ATTEMPT_STATUSES = {
    CommandExecutionAttemptStatus.STARTED,
    CommandExecutionAttemptStatus.RUNNING,
}


def execute_runtime_plan_for_attempt(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    worker_identifier: str,
    request_id: str | None = None,
    plan: ProtocolExecutionPlan | None = None,
) -> ExecuteRuntimePlanResponse:
    attempt = _get_active_attempt_for_execution(session, attempt_id=attempt_id)
    _ensure_worker_owns_attempt(attempt, worker_identifier)
    _ensure_attempt_is_executable(attempt)
    guard_metadata = build_runtime_execution_guard_metadata(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=worker_identifier,
        attempt_id=str(attempt.id),
    )
    attempt.execution_metadata = _merge_execution_metadata(
        attempt.execution_metadata,
        guard_metadata,
    )

    if plan is None:
        plan = build_runtime_plan_for_command(
            session,
            command_id=attempt.meter_command_id,
            worker_identifier=worker_identifier,
            request_id=request_id,
        )
    plan.execution_context.command_attempt_id = attempt.id
    plan.execution_context.worker_identifier = worker_identifier
    if request_id is not None:
        plan.execution_context.request_id = request_id

    adapter = get_runtime_adapter(plan.adapter_key)
    if not adapter.supports_plan(plan):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Adapter '{plan.adapter_key}' does not support the built execution plan.",
        )

    session_history = _get_or_create_session_history(session, attempt=attempt, plan=plan)
    _mark_attempt_running_with_session(session, attempt=attempt, session_history=session_history, plan=plan)

    try:
        result = adapter.execute(plan)
    except Exception as exc:
        result = _build_adapter_failure_result(plan=plan, session_history=session_history, exc=exc)

    session_result = result.session_result or _default_session_result_from_outcome(
        plan=plan,
        session_history=session_history,
        outcome=result.outcome,
        latest_error_code=result.latest_error_code,
        latest_error_message=result.latest_error_message,
    )
    _apply_session_result(session_history=session_history, session_result=session_result)

    ingestion_result = persist_runtime_result_telemetry(
        session,
        meter_id=plan.target.meter_id,
        command_id=plan.execution_context.command_id,
        attempt_id=attempt.id,
        session_history_id=session_history.id,
        result=result,
    )
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found for attempt.")
    post_processing = post_process_runtime_outcome(
        result=result,
        session_result=session_result,
        ingestion_result=ingestion_result,
        attempt=attempt,
        command=command,
    )
    normalized_summary = {
        **to_command_result_summary(result),
        "execution_guard": guard_metadata["runtime_execution_guard"],
        "post_processing": post_processing.summary,
        "ingestion": {
            "ingested_batch_id": (
                str(ingestion_result.ingested_batch.id) if ingestion_result.ingested_batch is not None else None
            ),
            "persisted_reading_count": (
                len(ingestion_result.ingested_batch.readings)
                if ingestion_result.ingested_batch is not None
                else 0
            ),
            "persisted_snapshot_count": (
                len(ingestion_result.ingested_batch.register_snapshots)
                if ingestion_result.ingested_batch is not None
                else 0
            ),
            "persisted_interval_count": ingestion_result.persisted_interval_count,
            "skipped_duplicate_interval_count": ingestion_result.skipped_duplicate_interval_count,
            "persisted_event_count": len(ingestion_result.ingested_events),
        },
    }
    execution_metadata = _merge_execution_metadata(
        attempt.execution_metadata,
        {
            "runtime_executor": {
                "adapter_key": plan.adapter_key,
                "intent": plan.intent.value,
                "placeholder": True,
                "outcome": result.outcome.value,
                "session_history_id": str(session_history.id),
                "post_processing": post_processing.summary,
            }
        },
    )

    finalized_attempt = _finalize_attempt(
        session,
        attempt_id=attempt.id,
        worker_identifier=worker_identifier,
        result=result,
        normalized_summary=normalized_summary,
        session_history_id=session_history.id,
        execution_metadata=execution_metadata,
        post_processing=post_processing,
    )
    finalized_attempt.execution_metadata = execution_metadata
    refreshed_command = session.get(MeterCommand, finalized_attempt.meter_command_id)
    if refreshed_command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found after finalization.")
    job_run = session.get(JobRun, finalized_attempt.job_run_id) if finalized_attempt.job_run_id is not None else None
    downstream_consumption = consume_downstream_signals(
        session,
        post_processing=post_processing,
        attempt=finalized_attempt,
        command=refreshed_command,
        session_history=session_history,
        job_run=job_run,
    )
    session.add_all([session_history, finalized_attempt])
    session.commit()
    session.refresh(finalized_attempt)
    session.refresh(session_history)

    return ExecuteRuntimePlanResponse(
        plan=plan,
        attempt=serialize_command_attempt(finalized_attempt),
        session=serialize_connectivity_session(session_history),
        outcome=result.outcome,
        result_summary=normalized_summary,
        response_snapshot=result.response_snapshot,
        ingested_batch=ingestion_result.ingested_batch,
        ingested_events=ingestion_result.ingested_events,
        persisted_interval_count=ingestion_result.persisted_interval_count,
        skipped_duplicate_interval_count=ingestion_result.skipped_duplicate_interval_count,
        post_processing=post_processing,
        downstream_consumption=downstream_consumption,
    )


def _get_active_attempt_for_execution(
    session: Session,
    *,
    attempt_id: uuid.UUID,
) -> CommandExecutionAttempt:
    attempt = session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.id == attempt_id)
        .with_for_update()
    )
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command execution attempt not found.")
    if attempt.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Command execution attempt is already finalized.",
        )
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime executor requires an attempt linked to a job run.",
        )
    return attempt


def _ensure_worker_owns_attempt(attempt: CommandExecutionAttempt, worker_identifier: str) -> None:
    if attempt.worker_identifier != worker_identifier:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt is owned by another worker.")


def _ensure_attempt_is_executable(attempt: CommandExecutionAttempt) -> None:
    if attempt.status not in EXECUTABLE_ATTEMPT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attempt cannot be executed from status {attempt.status.value}.",
        )


def _get_or_create_session_history(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    plan: ProtocolExecutionPlan,
) -> ConnectivitySessionHistory:
    if attempt.session_history_id is not None:
        session_history = session.get(ConnectivitySessionHistory, attempt.session_history_id)
        if session_history is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attempt references a missing connectivity session history row.",
            )
        if session_history.ended_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Attempt already references a finalized connectivity session.",
            )
        return session_history

    session_history = ConnectivitySessionHistory(
        meter_id=plan.target.meter_id,
        endpoint_id=plan.target.endpoint_id,
        protocol_association_profile_id=plan.target.protocol_association_profile_id,
        started_at=datetime.now(UTC),
        status=ConnectivitySessionStatus.STARTED,
        session_purpose=plan.session_purpose,
        request_id=plan.execution_context.request_id,
        correlation_id=plan.execution_context.correlation_id,
        handshake_stage=plan.stages[0].value if plan.stages else None,
        metadata_json={
            "adapter_key": plan.adapter_key,
            "intent": plan.intent.value,
            "placeholder": True,
            "stages": [stage.value for stage in plan.stages],
        },
    )
    session.add(session_history)
    session.flush()
    attempt.session_history_id = session_history.id
    attempt.endpoint_id = plan.target.endpoint_id
    session.add(attempt)
    return session_history


def _mark_attempt_running_with_session(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    session_history: ConnectivitySessionHistory,
    plan: ProtocolExecutionPlan,
) -> None:
    attempt.status = CommandExecutionAttemptStatus.RUNNING
    attempt.endpoint_id = plan.target.endpoint_id
    attempt.session_history_id = session_history.id
    attempt.execution_metadata = _merge_execution_metadata(
        attempt.execution_metadata,
        {
            "runtime_executor": {
                "adapter_key": plan.adapter_key,
                "phase": "invoking_adapter",
                "placeholder": True,
                "session_history_id": str(session_history.id),
            }
        },
    )
    session.add_all([attempt, session_history])
    session.commit()
    session.refresh(attempt)
    session.refresh(session_history)


def _build_adapter_failure_result(
    *,
    plan: ProtocolExecutionPlan,
    session_history: ConnectivitySessionHistory,
    exc: Exception,
) -> RuntimeCommandResult:
    return RuntimeCommandResult(
        outcome=RuntimeCommandOutcome.FAILED,
        result_summary={"adapter_key": plan.adapter_key, "placeholder": True, "exception_type": exc.__class__.__name__},
        response_snapshot={"exception": exc.__class__.__name__},
        latest_error_code="RUNTIME_ADAPTER_EXECUTION_ERROR",
        latest_error_message=str(exc),
        session_result=RuntimeSessionResult(
            status=ConnectivitySessionStatus.FAILED,
            session_purpose=plan.session_purpose,
            started_at=session_history.started_at,
            ended_at=datetime.now(UTC),
            request_id=plan.execution_context.request_id,
            correlation_id=plan.execution_context.correlation_id,
            handshake_stage=plan.stages[-1].value if plan.stages else None,
            error_code="RUNTIME_ADAPTER_EXECUTION_ERROR",
            error_message=str(exc),
            metadata={"adapter_key": plan.adapter_key, "placeholder": True},
        ),
    )


def _default_session_result_from_outcome(
    *,
    plan: ProtocolExecutionPlan,
    session_history: ConnectivitySessionHistory,
    outcome: RuntimeCommandOutcome,
    latest_error_code: str | None,
    latest_error_message: str | None,
) -> RuntimeSessionResult:
    status_map = {
        RuntimeCommandOutcome.SUCCEEDED: ConnectivitySessionStatus.SUCCEEDED,
        RuntimeCommandOutcome.FAILED: ConnectivitySessionStatus.FAILED,
        RuntimeCommandOutcome.TIMED_OUT: ConnectivitySessionStatus.TIMED_OUT,
        RuntimeCommandOutcome.CANCELLED: ConnectivitySessionStatus.CANCELLED,
    }
    return RuntimeSessionResult(
        status=status_map.get(outcome, ConnectivitySessionStatus.FAILED),
        session_purpose=plan.session_purpose,
        started_at=session_history.started_at,
        ended_at=datetime.now(UTC),
        request_id=plan.execution_context.request_id,
        correlation_id=plan.execution_context.correlation_id,
        handshake_stage=plan.stages[-1].value if plan.stages else None,
        error_code=latest_error_code,
        error_message=latest_error_message,
        metadata={"adapter_key": plan.adapter_key, "placeholder": True},
    )


def _apply_session_result(
    *,
    session_history: ConnectivitySessionHistory,
    session_result: RuntimeSessionResult,
) -> None:
    session_history.status = session_result.status
    session_history.session_purpose = session_result.session_purpose
    session_history.ended_at = session_result.ended_at or datetime.now(UTC)
    session_history.request_id = session_result.request_id
    session_history.correlation_id = session_result.correlation_id
    session_history.error_code = session_result.error_code
    session_history.error_message = session_result.error_message
    session_history.bytes_sent = session_result.bytes_sent
    session_history.bytes_received = session_result.bytes_received
    session_history.transport_latency_ms = session_result.transport_latency_ms
    session_history.handshake_stage = session_result.handshake_stage
    session_history.metadata_json = _merge_execution_metadata(
        session_history.metadata_json,
        session_result.metadata,
    )


def _finalize_attempt(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    worker_identifier: str,
    result: RuntimeCommandResult,
    normalized_summary: dict[str, object],
    session_history_id: uuid.UUID,
    execution_metadata: dict[str, object],
    post_processing,
) -> CommandExecutionAttempt:
    if result.outcome in {RuntimeCommandOutcome.SUCCEEDED, RuntimeCommandOutcome.PARTIAL}:
        return succeed_command_attempt(
            session,
            attempt_id=attempt_id,
            payload=CommandAttemptSucceedRequest(
                worker_identifier=worker_identifier,
                response_snapshot=result.response_snapshot,
                result_summary=normalized_summary,
                bytes_sent=result.session_result.bytes_sent if result.session_result else None,
                bytes_received=result.session_result.bytes_received if result.session_result else None,
                latency_ms=result.session_result.transport_latency_ms if result.session_result else None,
                session_history_id=session_history_id,
            ),
        )
    if result.outcome == RuntimeCommandOutcome.TIMED_OUT:
        return timeout_command_attempt(
            session,
            attempt_id=attempt_id,
            payload=CommandAttemptTimeoutRequest(
                worker_identifier=worker_identifier,
                error_message=result.latest_error_message,
                execution_metadata=execution_metadata,
                session_history_id=session_history_id,
                retry_delay_seconds=post_processing.retry.retry_delay_seconds,
            ),
            retry_allowed=post_processing.retry.retry_allowed_by_policy,
        )
    if result.outcome == RuntimeCommandOutcome.FAILED:
        return fail_command_attempt(
            session,
            attempt_id=attempt_id,
            payload=CommandAttemptFailRequest(
                worker_identifier=worker_identifier,
                error_code=result.latest_error_code,
                error_message=result.latest_error_message,
                response_snapshot=result.response_snapshot,
                execution_metadata=execution_metadata,
                bytes_sent=result.session_result.bytes_sent if result.session_result else None,
                bytes_received=result.session_result.bytes_received if result.session_result else None,
                latency_ms=result.session_result.transport_latency_ms if result.session_result else None,
                session_history_id=session_history_id,
                retry_delay_seconds=post_processing.retry.retry_delay_seconds,
            ),
            retry_allowed=post_processing.retry.retry_allowed_by_policy,
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Runtime executor does not support outcome {result.outcome.value} in this phase.",
    )
def _merge_execution_metadata(
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
