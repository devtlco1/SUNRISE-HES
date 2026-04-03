from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandCategory
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import serialize_command_attempt, serialize_meter_command
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.adapters import get_runtime_adapter
from app.runtime.contracts import (
    RuntimeAttemptDispositionResult,
    RuntimeClosureAttestationResult,
    RuntimeDeliveryContractResult,
    RuntimeDispatchEnvelopeResult,
    RuntimeExecutionGuardResult,
    RuntimeExecutionInvocationGateResult,
    RuntimeExecutionLeaseResult,
    RuntimeExecutionOutcomeResult,
    RuntimeExecutionSessionResult,
    RuntimeExecutionSessionStatus,
    RuntimeExternalizationEnvelopeResult,
    RuntimeFollowUpMaterializationResult,
    RuntimeOperationalClosureResult,
    RuntimePostProcessingBridgeResult,
    RuntimeProtocolAdapterSelectionResult,
    RuntimeProtocolDispatchRequestResult,
    RuntimeProtocolExecutionIntentResult,
    RuntimeProtocolExecutionObservationResult,
    RuntimeProtocolInterpretationResult,
    RuntimeProtocolInvocationResult,
    RuntimeProtocolReconciliationResult,
    RuntimePublicationContractResult,
    RuntimeRelayControlAdapterRequest,
    RuntimeRelayControlExecutionResult,
    RuntimeRelayControlOperation,
    RuntimeIntentType,
    RuntimeTerminalSettlementResult,
)
from app.runtime.schemas import (
    RuntimeRelayControlExecutionRequest,
    RuntimeRelayControlExecutionResponse,
)
from app.runtime.services.runtime_artifact_utils import (
    load_runtime_execution_guard,
    merge_runtime_metadata,
)
from app.runtime.services.runtime_plan_builder import build_runtime_plan_for_command


def execute_runtime_relay_control_adapter(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeRelayControlExecutionRequest,
) -> RuntimeRelayControlExecutionResponse:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command execution attempt not found.",
        )
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires an attempt linked to a job run.",
        )

    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )

    existing = _load_runtime_relay_control_execution(attempt.execution_metadata)
    if existing is not None:
        if existing.session_identifier != payload.session_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime relay control execution is already recorded for another session.",
            )
        if existing.executor_identifier != payload.executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime relay control execution is already owned by another executor.",
            )
        return RuntimeRelayControlExecutionResponse(
            result=existing.model_copy(update={"already_recorded": True}),
            job_run=serialize_job_run(job_run),
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(attempt),
        )

    session_result = _load_runtime_execution_session(attempt.execution_metadata)
    if session_result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a finalized runtime session.",
        )
    if session_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the finalized runtime session.",
        )
    if session_result.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if session_result.status != RuntimeExecutionSessionStatus.FINALIZED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a finalized runtime session.",
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
            detail="Runtime relay control requires a recorded runtime execution outcome.",
        )
    if outcome.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime execution outcome.",
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
            detail="Runtime relay control requires a recorded runtime attempt disposition.",
        )
    if disposition.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime attempt disposition.",
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
            detail="Runtime relay control requires a recorded runtime post-processing bridge.",
        )
    if post_processing.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime post-processing bridge.",
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
            detail="Runtime relay control requires a recorded runtime follow-up materialization.",
        )
    if materialization.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime follow-up materialization.",
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
            detail="Runtime relay control requires a recorded runtime operational closure.",
        )
    if closure.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime operational closure.",
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
            detail="Runtime relay control requires a recorded runtime protocol execution intent.",
        )
    if intent.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime protocol execution intent.",
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
            detail="Runtime relay control requires a recorded runtime protocol adapter selection.",
        )
    if selection.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime protocol adapter selection.",
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
            detail="Runtime relay control requires a recorded runtime protocol dispatch request.",
        )
    if dispatch_request.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime protocol dispatch request.",
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
            detail="Runtime relay control requires a recorded runtime protocol invocation result.",
        )
    if invocation_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime protocol invocation result.",
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
            detail="Runtime relay control requires a recorded runtime protocol execution observation.",
        )
    if observation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime protocol execution observation.",
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
            detail="Runtime relay control requires a recorded runtime protocol interpretation.",
        )
    if interpretation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime protocol interpretation.",
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

    reconciliation = _load_runtime_protocol_reconciliation(attempt.execution_metadata)
    if reconciliation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a recorded runtime protocol reconciliation.",
        )
    if reconciliation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime protocol reconciliation.",
        )
    if reconciliation.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation is owned by another executor.",
        )
    if reconciliation.reconciliation_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation is owned by another executor.",
        )

    settlement = _load_runtime_terminal_settlement(attempt.execution_metadata)
    if settlement is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a recorded runtime terminal settlement.",
        )
    if settlement.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime terminal settlement.",
        )
    if settlement.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime terminal settlement is owned by another executor.",
        )
    if settlement.settlement_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime terminal settlement is owned by another executor.",
        )

    attestation = _load_runtime_closure_attestation(attempt.execution_metadata)
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a recorded runtime closure attestation.",
        )
    if attestation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime closure attestation.",
        )
    if attestation.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime closure attestation is owned by another executor.",
        )
    if attestation.attestation_recorded_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime closure attestation is owned by another executor.",
        )

    publication_contract = _load_runtime_publication_contract(attempt.execution_metadata)
    if publication_contract is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a recorded runtime publication contract.",
        )
    if publication_contract.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime publication contract.",
        )
    if publication_contract.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime publication contract is owned by another executor.",
        )
    if (
        publication_contract.publication_contract_recorded_by_executor_identifier
        != payload.executor_identifier
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime publication contract is owned by another executor.",
        )

    externalization_envelope = _load_runtime_externalization_envelope(
        attempt.execution_metadata
    )
    if externalization_envelope is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a recorded runtime externalization envelope.",
        )
    if externalization_envelope.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime externalization envelope.",
        )
    if externalization_envelope.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime externalization envelope is owned by another executor.",
        )
    if (
        externalization_envelope.envelope_recorded_by_executor_identifier
        != payload.executor_identifier
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime externalization envelope is owned by another executor.",
        )

    delivery_contract = _load_runtime_delivery_contract(attempt.execution_metadata)
    if delivery_contract is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a recorded runtime delivery contract.",
        )
    if delivery_contract.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime delivery contract.",
        )
    if delivery_contract.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime delivery contract is owned by another executor.",
        )
    if (
        delivery_contract.delivery_contract_recorded_by_executor_identifier
        != payload.executor_identifier
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime delivery contract is owned by another executor.",
        )

    dispatch_envelope = _load_runtime_dispatch_envelope(attempt.execution_metadata)
    if dispatch_envelope is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a recorded runtime dispatch envelope.",
        )
    if dispatch_envelope.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control does not match the recorded runtime dispatch envelope.",
        )
    if dispatch_envelope.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime dispatch envelope is owned by another executor.",
        )
    if (
        dispatch_envelope.dispatch_envelope_recorded_by_executor_identifier
        != payload.executor_identifier
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime dispatch envelope is owned by another executor.",
        )
    if (
        dispatch_envelope.delivery_contract_record_id
        != delivery_contract.delivery_contract_record_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime dispatch envelope does not match the recorded runtime delivery contract.",
        )

    _validate_runtime_relay_control_context(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=payload.executor_identifier,
    )

    plan = build_runtime_plan_for_command(
        session,
        command_id=attempt.meter_command_id,
        worker_identifier=payload.executor_identifier,
        request_id=payload.request_id,
    )
    plan.execution_context.command_attempt_id = attempt.id
    plan.execution_context.worker_identifier = payload.executor_identifier

    if plan.intent not in {RuntimeIntentType.DISCONNECT, RuntimeIntentType.RECONNECT}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control only supports disconnect and reconnect commands.",
        )
    if command.command_template.category not in {
        CommandCategory.REMOTE_DISCONNECT,
        CommandCategory.REMOTE_RECONNECT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control only supports relay-control command categories.",
        )

    adapter_request = _build_runtime_relay_control_adapter_request(
        plan=plan,
        dispatch_envelope=dispatch_envelope,
        delivery_contract=delivery_contract,
        externalization_envelope=externalization_envelope,
        publication_contract=publication_contract,
        attestation=attestation,
        settlement=settlement,
        reconciliation=reconciliation,
        interpretation=interpretation,
        observation=observation,
        invocation_result=invocation_result,
        dispatch_request=dispatch_request,
        selection=selection,
        intent=intent,
        closure=closure,
        materialization=materialization,
        post_processing=post_processing,
        disposition=disposition,
        outcome=outcome,
        session_result=session_result,
    )

    adapter = get_runtime_adapter(plan.adapter_key)
    if not adapter.supports_relay_control(adapter_request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Adapter '{plan.adapter_key}' does not support the relay control vertical slice.",
        )

    try:
        result = adapter.execute_relay_control(adapter_request)
    except (NotImplementedError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    relay_control_payload = {"runtime_relay_control_execution": result.model_dump(mode="json")}
    attempt.execution_metadata = merge_runtime_metadata(
        attempt.execution_metadata,
        relay_control_payload,
    )
    command.result_summary = merge_runtime_metadata(command.result_summary, relay_control_payload)
    job_run.result_summary = merge_runtime_metadata(job_run.result_summary, relay_control_payload)
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(command)
    session.refresh(job_run)
    return RuntimeRelayControlExecutionResponse(
        result=result,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _build_runtime_relay_control_adapter_request(
    *,
    plan,
    dispatch_envelope: RuntimeDispatchEnvelopeResult,
    delivery_contract: RuntimeDeliveryContractResult,
    externalization_envelope: RuntimeExternalizationEnvelopeResult,
    publication_contract: RuntimePublicationContractResult,
    attestation: RuntimeClosureAttestationResult,
    settlement: RuntimeTerminalSettlementResult,
    reconciliation: RuntimeProtocolReconciliationResult,
    interpretation: RuntimeProtocolInterpretationResult,
    observation: RuntimeProtocolExecutionObservationResult,
    invocation_result: RuntimeProtocolInvocationResult,
    dispatch_request: RuntimeProtocolDispatchRequestResult,
    selection: RuntimeProtocolAdapterSelectionResult,
    intent: RuntimeProtocolExecutionIntentResult,
    closure: RuntimeOperationalClosureResult,
    materialization: RuntimeFollowUpMaterializationResult,
    post_processing: RuntimePostProcessingBridgeResult,
    disposition: RuntimeAttemptDispositionResult,
    outcome: RuntimeExecutionOutcomeResult,
    session_result: RuntimeExecutionSessionResult,
) -> RuntimeRelayControlAdapterRequest:
    operation = (
        RuntimeRelayControlOperation.DISCONNECT
        if plan.intent == RuntimeIntentType.DISCONNECT
        else RuntimeRelayControlOperation.RECONNECT
    )
    return RuntimeRelayControlAdapterRequest(
        adapter_key=plan.adapter_key,
        protocol_family=plan.protocol_family,
        operation=operation,
        command_category=plan.command.category,
        execution_context=plan.execution_context,
        target=plan.target,
        transport=plan.transport,
        security=plan.security,
        protocol_profile_code=plan.protocol_profile_code,
        iec62056_21_enabled=plan.iec62056_21_enabled,
        iec_device_address=plan.iec_device_address,
        iec_baud_rate=plan.iec_baud_rate,
        client_address=plan.client_address,
        server_address=plan.server_address,
        server_address_size=plan.server_address_size,
        protocol_settings=plan.protocol_settings,
        protocol_defaults=plan.protocol_defaults,
        request_payload=plan.command.request_payload,
        normalized_payload=plan.command.normalized_payload,
        dispatch_envelope_record_id=dispatch_envelope.dispatch_envelope_record_id,
        trace_references={
            "session_identifier": session_result.session_identifier,
            "delivery_contract_record_id": delivery_contract.delivery_contract_record_id,
            "envelope_record_id": externalization_envelope.envelope_record_id,
            "publication_contract_record_id": publication_contract.publication_contract_record_id,
            "attestation_record_id": attestation.attestation_record_id,
            "settlement_record_id": settlement.settlement_record_id,
            "reconciliation_record_id": reconciliation.reconciliation_record_id,
            "interpretation_record_id": interpretation.interpretation_record_id,
            "observation_record_id": observation.observation_record_id,
            "invocation_result_record_id": invocation_result.invocation_result_record_id,
            "dispatch_request_record_id": dispatch_request.dispatch_request_record_id,
            "selection_record_id": selection.selection_record_id,
            "intent_record_id": intent.intent_record_id,
            "closure_record_id": closure.closure_record_id,
            "materialization_record_id": materialization.materialization_record_id,
            "post_processing_record_id": post_processing.post_processing_record_id,
            "disposition_record_id": disposition.disposition_record_id,
            "outcome_record_id": outcome.outcome_record_id,
        },
        lineage=session_result.lineage,
    )


def _validate_runtime_relay_control_context(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
) -> None:
    lease = _load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a runtime lease.",
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
            detail="Runtime relay control requires a runtime invocation gate.",
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

    guard = load_runtime_execution_guard(execution_metadata)
    if guard is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime relay control requires a runtime execution guard.",
        )
    if guard.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard is owned by another executor.",
        )
    if guard.lease_record_id != lease.lease_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution guard does not match the runtime lease.",
        )
    if guard.invocation_record_id != invocation.invocation_record_id:
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


def _load_runtime_terminal_settlement(
    execution_metadata: dict[str, object] | None,
) -> RuntimeTerminalSettlementResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_terminal_settlement")
    if not isinstance(payload, dict):
        return None
    return RuntimeTerminalSettlementResult.model_validate(payload)


def _load_runtime_closure_attestation(
    execution_metadata: dict[str, object] | None,
) -> RuntimeClosureAttestationResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_closure_attestation")
    if not isinstance(payload, dict):
        return None
    return RuntimeClosureAttestationResult.model_validate(payload)


def _load_runtime_publication_contract(
    execution_metadata: dict[str, object] | None,
) -> RuntimePublicationContractResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_publication_contract")
    if not isinstance(payload, dict):
        return None
    return RuntimePublicationContractResult.model_validate(payload)


def _load_runtime_externalization_envelope(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExternalizationEnvelopeResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_externalization_envelope")
    if not isinstance(payload, dict):
        return None
    return RuntimeExternalizationEnvelopeResult.model_validate(payload)


def _load_runtime_delivery_contract(
    execution_metadata: dict[str, object] | None,
) -> RuntimeDeliveryContractResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_delivery_contract")
    if not isinstance(payload, dict):
        return None
    return RuntimeDeliveryContractResult.model_validate(payload)


def _load_runtime_dispatch_envelope(
    execution_metadata: dict[str, object] | None,
) -> RuntimeDispatchEnvelopeResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_dispatch_envelope")
    if not isinstance(payload, dict):
        return None
    return RuntimeDispatchEnvelopeResult.model_validate(payload)


def _load_runtime_relay_control_execution(
    execution_metadata: dict[str, object] | None,
) -> RuntimeRelayControlExecutionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_relay_control_execution")
    if not isinstance(payload, dict):
        return None
    return RuntimeRelayControlExecutionResult.model_validate(payload)


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
