from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import serialize_command_attempt, serialize_meter_command
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.contracts import (
    RuntimeAttemptDispositionResult,
    RuntimeExecutionInvocationGateResult,
    RuntimeExecutionLeaseResult,
    RuntimeExecutionOutcomeResult,
    RuntimeExecutionSessionResult,
    RuntimeExecutionSessionStatus,
    RuntimeFollowUpMaterializationResult,
    RuntimeOperationalClosureResult,
    RuntimeOperationalClosureStatus,
    RuntimePostProcessingBridgeResult,
)
from app.runtime.schemas import (
    RuntimeOperationalClosureBridgeRequest,
    RuntimeOperationalClosureBridgeResponse,
)


def bridge_runtime_follow_up_materialization_to_operational_closure(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeOperationalClosureBridgeRequest,
) -> RuntimeOperationalClosureBridgeResponse:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command execution attempt not found.",
        )
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure bridge requires an attempt linked to a job run.",
        )
    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )

    existing = _load_runtime_operational_closure(attempt.execution_metadata)
    if existing is not None:
        if existing.session_identifier != payload.session_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime operational closure is already recorded for another session.",
            )
        if existing.executor_identifier != payload.executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime operational closure is already owned by another executor.",
            )
        return RuntimeOperationalClosureBridgeResponse(
            result=existing.model_copy(update={"already_recorded": True}),
            job_run=serialize_job_run(job_run),
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(attempt),
        )

    session_result = _load_runtime_execution_session(attempt.execution_metadata)
    if session_result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure requires a finalized runtime session.",
        )
    if session_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure does not match the finalized runtime session.",
        )
    if session_result.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if session_result.status != RuntimeExecutionSessionStatus.FINALIZED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure requires a finalized runtime session.",
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
            detail="Runtime operational closure requires a recorded runtime execution outcome.",
        )
    if outcome.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure does not match the recorded runtime execution outcome.",
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

    disposition = _load_runtime_attempt_disposition(attempt.execution_metadata)
    if disposition is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure requires a recorded runtime attempt disposition.",
        )
    if disposition.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure does not match the recorded runtime attempt disposition.",
        )
    if disposition.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition is owned by another executor.",
        )
    if disposition.disposition_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime attempt disposition is owned by another executor.",
        )

    post_processing = _load_runtime_post_processing_bridge(attempt.execution_metadata)
    if post_processing is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure requires a recorded runtime post-processing bridge.",
        )
    if post_processing.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure does not match the recorded runtime post-processing bridge.",
        )
    if post_processing.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime post-processing bridge is owned by another executor.",
        )
    if post_processing.post_processing_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime post-processing bridge is owned by another executor.",
        )

    materialization = _load_runtime_follow_up_materialization(attempt.execution_metadata)
    if materialization is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure requires a recorded runtime follow-up materialization.",
        )
    if materialization.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure does not match the recorded runtime follow-up materialization.",
        )
    if materialization.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime follow-up materialization is owned by another executor.",
        )
    if materialization.materialized_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime follow-up materialization is owned by another executor.",
        )

    _validate_runtime_operational_closure_context(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )

    result = _build_runtime_operational_closure_result(
        attempt=attempt,
        outcome=outcome,
        disposition=disposition,
        post_processing=post_processing,
        materialization=materialization,
        payload=payload,
    )
    closure_payload = {"runtime_operational_closure": result.model_dump(mode="json")}
    attempt.execution_metadata = _merge_dicts(attempt.execution_metadata, closure_payload)
    command.result_summary = _merge_dicts(command.result_summary, closure_payload)
    job_run.result_summary = _merge_dicts(job_run.result_summary, closure_payload)
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(command)
    session.refresh(job_run)
    return RuntimeOperationalClosureBridgeResponse(
        result=result,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _build_runtime_operational_closure_result(
    *,
    attempt: CommandExecutionAttempt,
    outcome: RuntimeExecutionOutcomeResult,
    disposition: RuntimeAttemptDispositionResult,
    post_processing: RuntimePostProcessingBridgeResult,
    materialization: RuntimeFollowUpMaterializationResult,
    payload: RuntimeOperationalClosureBridgeRequest,
) -> RuntimeOperationalClosureResult:
    return RuntimeOperationalClosureResult(
        status=RuntimeOperationalClosureStatus.RECORDED,
        closure_record_id=(
            "runtime-operational-closure:"
            f"{attempt.id}:{materialization.materialization_record_id}"
        ),
        session_identifier=materialization.session_identifier,
        materialization_record_id=materialization.materialization_record_id,
        post_processing_record_id=post_processing.post_processing_record_id,
        disposition_record_id=disposition.disposition_record_id,
        outcome_record_id=outcome.outcome_record_id,
        executor_identifier=payload.executor_identifier,
        job_run_id=str(attempt.job_run_id),
        related_command_id=str(attempt.meter_command_id),
        command_attempt_id=str(attempt.id),
        terminal_outcome=materialization.terminal_outcome,
        downstream_state=materialization.downstream_state,
        included_follow_up_descriptor_types=[
            descriptor.descriptor_type.value
            for descriptor in materialization.follow_up_descriptors
        ],
        closure_recorded_at=datetime.now(UTC).isoformat(),
        closure_recorded_by_executor_identifier=payload.executor_identifier,
        closure_reason=payload.closure_reason,
        already_recorded=False,
        summary=(
            "Runtime follow-up materialization is consolidated into a durable "
            "placeholder operational closure summary without downstream execution."
        ),
        lineage=outcome.lineage,
    )


def _validate_runtime_operational_closure_context(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
) -> None:
    lease = _load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure requires a runtime lease.",
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
            detail="Runtime operational closure requires a runtime invocation gate.",
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
            detail="Runtime operational closure requires a runtime execution guard.",
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


def _load_runtime_post_processing_bridge(
    execution_metadata: dict[str, object] | None,
) -> RuntimePostProcessingBridgeResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_post_processing_bridge")
    if not isinstance(payload, dict):
        return None
    return RuntimePostProcessingBridgeResult.model_validate(payload)


def _load_runtime_follow_up_materialization(
    execution_metadata: dict[str, object] | None,
) -> RuntimeFollowUpMaterializationResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_follow_up_materialization")
    if not isinstance(payload, dict):
        return None
    return RuntimeFollowUpMaterializationResult.model_validate(payload)


def _load_runtime_operational_closure(
    execution_metadata: dict[str, object] | None,
) -> RuntimeOperationalClosureResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_operational_closure")
    if not isinstance(payload, dict):
        return None
    return RuntimeOperationalClosureResult.model_validate(payload)


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
