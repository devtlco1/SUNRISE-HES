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
    RuntimePostProcessingBridgeResult,
    RuntimeProtocolAdapterSelectionResult,
    RuntimeProtocolDispatchRequestResult,
    RuntimeProtocolExecutionIntentResult,
    RuntimeProtocolExecutionObservationResult,
    RuntimeProtocolInterpretationResult,
    RuntimeProtocolInvocationResult,
    RuntimeProtocolReconciliationFamily,
    RuntimeProtocolReconciliationPayload,
    RuntimeProtocolReconciliationResult,
    RuntimeProtocolReconciliationState,
    RuntimeProtocolReconciliationStatus,
    RuntimeProtocolRuntimeSemanticReconciliationClassification,
)
from app.runtime.schemas import (
    RuntimeProtocolReconciliationBridgeRequest,
    RuntimeProtocolReconciliationBridgeResponse,
)


def bridge_runtime_protocol_interpretation_to_reconciliation(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolReconciliationBridgeRequest,
) -> RuntimeProtocolReconciliationBridgeResponse:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command execution attempt not found.",
        )
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires an attempt linked to a job run.",
        )
    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )

    existing = _load_runtime_protocol_reconciliation(attempt.execution_metadata)
    if existing is not None:
        if existing.session_identifier != payload.session_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime protocol reconciliation is already recorded for another session.",
            )
        if existing.executor_identifier != payload.executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime protocol reconciliation is already owned by another executor.",
            )
        return RuntimeProtocolReconciliationBridgeResponse(
            result=existing.model_copy(update={"already_recorded": True}),
            job_run=serialize_job_run(job_run),
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(attempt),
        )

    session_result = _load_runtime_execution_session(attempt.execution_metadata)
    if session_result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a finalized runtime session.",
        )
    if session_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the finalized runtime session.",
        )
    if session_result.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if session_result.status != RuntimeExecutionSessionStatus.FINALIZED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a finalized runtime session.",
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
            detail="Runtime protocol reconciliation requires a recorded runtime execution outcome.",
        )
    if outcome.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime execution outcome.",
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
            detail="Runtime protocol reconciliation requires a recorded runtime attempt disposition.",
        )
    if disposition.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime attempt disposition.",
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
            detail="Runtime protocol reconciliation requires a recorded runtime post-processing bridge.",
        )
    if post_processing.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime post-processing bridge.",
        )
    if post_processing.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime post-processing bridge is owned by another executor.",
        )
    if (
        post_processing.post_processing_recorded_by_executor_identifier
        != payload.executor_identifier
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime post-processing bridge is owned by another executor.",
        )

    materialization = _load_runtime_follow_up_materialization(attempt.execution_metadata)
    if materialization is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime follow-up materialization.",
        )
    if materialization.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime follow-up materialization.",
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

    closure = _load_runtime_operational_closure(attempt.execution_metadata)
    if closure is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime operational closure.",
        )
    if closure.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime operational closure.",
        )
    if closure.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure is owned by another executor.",
        )
    if closure.closure_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime operational closure is owned by another executor.",
        )

    intent = _load_runtime_protocol_execution_intent(attempt.execution_metadata)
    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime protocol execution intent.",
        )
    if intent.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime protocol execution intent.",
        )
    if intent.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol execution intent is owned by another executor.",
        )
    if intent.intent_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol execution intent is owned by another executor.",
        )

    selection = _load_runtime_protocol_adapter_selection(attempt.execution_metadata)
    if selection is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime protocol adapter selection.",
        )
    if selection.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime protocol adapter selection.",
        )
    if selection.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol adapter selection is owned by another executor.",
        )
    if selection.selection_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol adapter selection is owned by another executor.",
        )

    dispatch_request = _load_runtime_protocol_dispatch_request(attempt.execution_metadata)
    if dispatch_request is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime protocol dispatch request.",
        )
    if dispatch_request.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime protocol dispatch request.",
        )
    if dispatch_request.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol dispatch request is owned by another executor.",
        )
    if dispatch_request.request_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol dispatch request is owned by another executor.",
        )

    invocation_result = _load_runtime_protocol_invocation_result(attempt.execution_metadata)
    if invocation_result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime protocol invocation result.",
        )
    if invocation_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime protocol invocation result.",
        )
    if invocation_result.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol invocation result is owned by another executor.",
        )
    if invocation_result.result_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol invocation result is owned by another executor.",
        )

    observation = _load_runtime_protocol_execution_observation(attempt.execution_metadata)
    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime protocol execution observation.",
        )
    if observation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime protocol execution observation.",
        )
    if observation.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol execution observation is owned by another executor.",
        )
    if observation.observation_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol execution observation is owned by another executor.",
        )

    interpretation = _load_runtime_protocol_interpretation(attempt.execution_metadata)
    if interpretation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a recorded runtime protocol interpretation.",
        )
    if interpretation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation does not match the recorded runtime protocol interpretation.",
        )
    if interpretation.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol interpretation is owned by another executor.",
        )
    if interpretation.interpretation_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol interpretation is owned by another executor.",
        )
    if interpretation.observation_record_id != observation.observation_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol interpretation does not match the recorded runtime protocol execution observation.",
        )

    _validate_runtime_protocol_reconciliation_context(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )

    result = _build_runtime_protocol_reconciliation_result(
        attempt=attempt,
        interpretation=interpretation,
        payload=payload,
    )
    reconciliation_payload = {"runtime_protocol_reconciliation": result.model_dump(mode="json")}
    attempt.execution_metadata = _merge_dicts(attempt.execution_metadata, reconciliation_payload)
    command.result_summary = _merge_dicts(command.result_summary, reconciliation_payload)
    job_run.result_summary = _merge_dicts(job_run.result_summary, reconciliation_payload)
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(command)
    session.refresh(job_run)
    return RuntimeProtocolReconciliationBridgeResponse(
        result=result,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _build_runtime_protocol_reconciliation_result(
    *,
    attempt: CommandExecutionAttempt,
    interpretation: RuntimeProtocolInterpretationResult,
    payload: RuntimeProtocolReconciliationBridgeRequest,
) -> RuntimeProtocolReconciliationResult:
    interpretation_payload = interpretation.interpretation_payload
    return RuntimeProtocolReconciliationResult(
        status=RuntimeProtocolReconciliationStatus.RECORDED,
        reconciliation_record_id=(
            "runtime-protocol-reconciliation:"
            f"{attempt.id}:{interpretation.interpretation_record_id}"
        ),
        session_identifier=interpretation.session_identifier,
        interpretation_record_id=interpretation.interpretation_record_id,
        observation_record_id=interpretation.observation_record_id,
        invocation_result_record_id=interpretation.invocation_result_record_id,
        dispatch_request_record_id=interpretation.dispatch_request_record_id,
        selection_record_id=interpretation.selection_record_id,
        intent_record_id=interpretation.intent_record_id,
        closure_record_id=interpretation.closure_record_id,
        materialization_record_id=interpretation.materialization_record_id,
        post_processing_record_id=interpretation.post_processing_record_id,
        disposition_record_id=interpretation.disposition_record_id,
        outcome_record_id=interpretation.outcome_record_id,
        executor_identifier=payload.executor_identifier,
        job_run_id=str(attempt.job_run_id),
        related_command_id=str(attempt.meter_command_id),
        command_attempt_id=str(attempt.id),
        terminal_outcome=interpretation.terminal_outcome,
        downstream_state=interpretation.downstream_state,
        reconciliation_key="placeholder.protocol.runtime-reconciliation",
        reconciliation_family=(
            RuntimeProtocolReconciliationFamily.PLACEHOLDER_PROTOCOL_RUNTIME_RECONCILIATION
        ),
        reconciliation_payload=RuntimeProtocolReconciliationPayload(
            schema_version="placeholder-runtime-protocol-reconciliation.v1",
            reconciliation_state=(
                RuntimeProtocolReconciliationState.PLACEHOLDER_RUNTIME_RECONCILIATION_RECORDED
            ),
            runtime_reconciliation_mode=interpretation_payload.runtime_meaning_mode,
            adapter_family=interpretation_payload.adapter_family,
            capability_profile=interpretation_payload.capability_profile,
            runtime_semantic_reconciliation_classification=(
                RuntimeProtocolRuntimeSemanticReconciliationClassification.PLACEHOLDER_PROTOCOL_MEANING_RECONCILED
            ),
            placeholder_chain_references={
                "interpretation_record_id": interpretation.interpretation_record_id,
                "observation_record_id": interpretation.observation_record_id,
                "invocation_result_record_id": interpretation.invocation_result_record_id,
                "dispatch_request_record_id": interpretation.dispatch_request_record_id,
                "selection_record_id": interpretation.selection_record_id,
                "intent_record_id": interpretation.intent_record_id,
                "closure_record_id": interpretation.closure_record_id,
                "materialization_record_id": interpretation.materialization_record_id,
                "post_processing_record_id": interpretation.post_processing_record_id,
                "disposition_record_id": interpretation.disposition_record_id,
                "outcome_record_id": interpretation.outcome_record_id,
            },
        ),
        included_follow_up_descriptor_types=interpretation.included_follow_up_descriptor_types,
        reconciliation_recorded_at=datetime.now(UTC).isoformat(),
        reconciliation_recorded_by_executor_identifier=payload.executor_identifier,
        reconciliation_reason=payload.reconciliation_reason,
        already_recorded=False,
        summary=(
            "Runtime protocol interpretation is converted into a durable placeholder "
            "runtime reconciliation artifact without executing any live protocol reconciliation logic."
        ),
        lineage=interpretation.lineage,
    )


def _validate_runtime_protocol_reconciliation_context(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
) -> None:
    lease = _load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation requires a runtime lease.",
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
            detail="Runtime protocol reconciliation requires a runtime invocation gate.",
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
            detail="Runtime protocol reconciliation requires a runtime execution guard.",
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


def _load_runtime_protocol_execution_intent(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProtocolExecutionIntentResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_protocol_execution_intent")
    if not isinstance(payload, dict):
        return None
    return RuntimeProtocolExecutionIntentResult.model_validate(payload)


def _load_runtime_protocol_adapter_selection(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProtocolAdapterSelectionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_protocol_adapter_selection")
    if not isinstance(payload, dict):
        return None
    return RuntimeProtocolAdapterSelectionResult.model_validate(payload)


def _load_runtime_protocol_dispatch_request(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProtocolDispatchRequestResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_protocol_dispatch_request")
    if not isinstance(payload, dict):
        return None
    return RuntimeProtocolDispatchRequestResult.model_validate(payload)


def _load_runtime_protocol_invocation_result(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProtocolInvocationResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_protocol_invocation_result")
    if not isinstance(payload, dict):
        return None
    return RuntimeProtocolInvocationResult.model_validate(payload)


def _load_runtime_protocol_execution_observation(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProtocolExecutionObservationResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_protocol_execution_observation")
    if not isinstance(payload, dict):
        return None
    return RuntimeProtocolExecutionObservationResult.model_validate(payload)


def _load_runtime_protocol_interpretation(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProtocolInterpretationResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_protocol_interpretation")
    if not isinstance(payload, dict):
        return None
    return RuntimeProtocolInterpretationResult.model_validate(payload)


def _load_runtime_protocol_reconciliation(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProtocolReconciliationResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_protocol_reconciliation")
    if not isinstance(payload, dict):
        return None
    return RuntimeProtocolReconciliationResult.model_validate(payload)


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
