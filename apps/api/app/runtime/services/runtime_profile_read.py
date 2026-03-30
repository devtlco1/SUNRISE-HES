from __future__ import annotations

import uuid

import app.runtime.services.runtime_relay_control as relay_helpers
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandCategory
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import serialize_command_attempt, serialize_meter_command
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.adapters import get_runtime_adapter
from app.runtime.contracts import (
    RuntimeCaptureLoadProfileExecutionCategory,
    RuntimeCaptureLoadProfileExecutionDigest,
    RuntimeCaptureLoadProfileTerminalStatus,
    RuntimeCaptureLoadProfileTerminalStatusCategory,
    RuntimeAttemptDispositionResult,
    RuntimeCommandOutcome,
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
    RuntimeProfileReadAdapterRequest,
    RuntimeProfileReadExecutionResult,
    RuntimeProfileReadOperation,
    RuntimeProtocolAdapterCapability,
    RuntimeProtocolAdapterSelectionResult,
    RuntimeProtocolDispatchRequestResult,
    RuntimeProtocolExecutionIntentResult,
    RuntimeProtocolExecutionObservationResult,
    RuntimeProtocolInterpretationResult,
    RuntimeProtocolInvocationResult,
    RuntimeProtocolReconciliationResult,
    RuntimePublicationContractResult,
    RuntimeIntentType,
    RuntimeTerminalSettlementResult,
)
from app.runtime.schemas import (
    RuntimeProfileReadExecutionRequest,
    RuntimeProfileReadExecutionResponse,
)
from app.runtime.services.runtime_artifact_utils import (
    load_runtime_execution_guard,
    merge_runtime_metadata,
)
from app.runtime.services.runtime_plan_builder import build_runtime_plan_for_command


def execute_runtime_profile_read_adapter(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: RuntimeProfileReadExecutionRequest,
) -> RuntimeProfileReadExecutionResponse:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command execution attempt not found.",
        )
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires an attempt linked to a job run.",
        )

    job_run = get_job_run(session, attempt.job_run_id)
    command = session.get(MeterCommand, attempt.meter_command_id)
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found for attempt.",
        )

    existing = _load_runtime_profile_read_execution(attempt.execution_metadata)
    if existing is not None:
        if existing.session_identifier != payload.session_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime profile read execution is already recorded for another session.",
            )
        if existing.executor_identifier != payload.executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime profile read execution is already owned by another executor.",
            )
        digest = _load_runtime_capture_load_profile_execution_digest(
            attempt.execution_metadata
        )
        if digest is None:
            digest = _project_capture_load_profile_execution_digest(existing)
            digest_payload = {
                "runtime_capture_load_profile_execution_digest": digest.model_dump(
                    mode="json"
                )
            }
            attempt.execution_metadata = merge_runtime_metadata(
                attempt.execution_metadata,
                digest_payload,
            )
            command.result_summary = merge_runtime_metadata(command.result_summary, digest_payload)
            job_run.result_summary = merge_runtime_metadata(job_run.result_summary, digest_payload)
            session.add_all([attempt, command, job_run])
            session.commit()
            session.refresh(attempt)
            session.refresh(command)
            session.refresh(job_run)
        terminal_status = _load_runtime_capture_load_profile_terminal_status(
            attempt.execution_metadata
        )
        if terminal_status is None:
            terminal_status = _project_capture_load_profile_terminal_status(
                existing,
                digest,
            )
            terminal_status_payload = {
                "runtime_capture_load_profile_terminal_status": terminal_status.model_dump(
                    mode="json"
                )
            }
            attempt.execution_metadata = merge_runtime_metadata(
                attempt.execution_metadata,
                terminal_status_payload,
            )
            command.result_summary = merge_runtime_metadata(
                command.result_summary,
                terminal_status_payload,
            )
            job_run.result_summary = merge_runtime_metadata(
                job_run.result_summary,
                terminal_status_payload,
            )
            session.add_all([attempt, command, job_run])
            session.commit()
            session.refresh(attempt)
            session.refresh(command)
            session.refresh(job_run)
        return RuntimeProfileReadExecutionResponse(
            result=existing.model_copy(
                update={
                    "already_recorded": True,
                    "capture_load_profile_execution_digest": digest,
                    "capture_load_profile_terminal_status": terminal_status,
                }
            ),
            job_run=serialize_job_run(job_run),
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(attempt),
        )

    session_result = relay_helpers._load_runtime_execution_session(attempt.execution_metadata)
    if session_result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a finalized runtime session.",
        )
    if session_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the finalized runtime session.",
        )
    if session_result.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution session is owned by another executor.",
        )
    if session_result.status != RuntimeExecutionSessionStatus.FINALIZED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a finalized runtime session.",
        )
    if session_result.finalized_by_executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution finalized session is owned by another executor.",
        )

    outcome = relay_helpers._load_runtime_execution_outcome(attempt.execution_metadata)
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime execution outcome.",
        )
    if outcome.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime execution outcome.",
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

    disposition = relay_helpers._load_runtime_attempt_disposition(attempt.execution_metadata)
    if disposition is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime attempt disposition.",
        )
    if disposition.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime attempt disposition.",
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

    post_processing = relay_helpers._load_runtime_post_processing_bridge(
        attempt.execution_metadata
    )
    if post_processing is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime post-processing bridge.",
        )
    if post_processing.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime post-processing bridge.",
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

    materialization = relay_helpers._load_runtime_follow_up_materialization(
        attempt.execution_metadata
    )
    if materialization is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime follow-up materialization.",
        )
    if materialization.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime follow-up materialization.",
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

    closure = relay_helpers._load_runtime_operational_closure(attempt.execution_metadata)
    if closure is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime operational closure.",
        )
    if closure.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime operational closure.",
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

    intent = relay_helpers._load_runtime_protocol_execution_intent(
        attempt.execution_metadata
    )
    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime protocol execution intent.",
        )
    if intent.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime protocol execution intent.",
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

    selection = relay_helpers._load_runtime_protocol_adapter_selection(
        attempt.execution_metadata
    )
    if selection is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime protocol adapter selection.",
        )
    if selection.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime protocol adapter selection.",
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
    if (
        RuntimeProtocolAdapterCapability.SUPPORTS_PLACEHOLDER_READ_PROFILE
        not in selection.supported_placeholder_capabilities
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol adapter selection does not authorize the profile-read vertical slice.",
        )

    dispatch_request = relay_helpers._load_runtime_protocol_dispatch_request(
        attempt.execution_metadata
    )
    if dispatch_request is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime protocol dispatch request.",
        )
    if dispatch_request.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime protocol dispatch request.",
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

    invocation_result = relay_helpers._load_runtime_protocol_invocation_result(
        attempt.execution_metadata
    )
    if invocation_result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime protocol invocation result.",
        )
    if invocation_result.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime protocol invocation result.",
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

    observation = relay_helpers._load_runtime_protocol_execution_observation(
        attempt.execution_metadata
    )
    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime protocol execution observation.",
        )
    if observation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime protocol execution observation.",
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

    interpretation = relay_helpers._load_runtime_protocol_interpretation(
        attempt.execution_metadata
    )
    if interpretation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime protocol interpretation.",
        )
    if interpretation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime protocol interpretation.",
        )
    if interpretation.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol interpretation is owned by another executor.",
        )
    if (
        interpretation.interpretation_recorded_by_executor_identifier
        != payload.executor_identifier
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol interpretation is owned by another executor.",
        )

    reconciliation = relay_helpers._load_runtime_protocol_reconciliation(
        attempt.execution_metadata
    )
    if reconciliation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime protocol reconciliation.",
        )
    if reconciliation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime protocol reconciliation.",
        )
    if reconciliation.executor_identifier != payload.executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation is owned by another executor.",
        )
    if (
        reconciliation.reconciliation_recorded_by_executor_identifier
        != payload.executor_identifier
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime protocol reconciliation is owned by another executor.",
        )

    settlement = relay_helpers._load_runtime_terminal_settlement(attempt.execution_metadata)
    if settlement is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime terminal settlement.",
        )
    if settlement.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime terminal settlement.",
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

    attestation = relay_helpers._load_runtime_closure_attestation(
        attempt.execution_metadata
    )
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime closure attestation.",
        )
    if attestation.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime closure attestation.",
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

    publication_contract = relay_helpers._load_runtime_publication_contract(
        attempt.execution_metadata
    )
    if publication_contract is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime publication contract.",
        )
    if publication_contract.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime publication contract.",
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

    externalization_envelope = relay_helpers._load_runtime_externalization_envelope(
        attempt.execution_metadata
    )
    if externalization_envelope is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime externalization envelope.",
        )
    if externalization_envelope.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime externalization envelope.",
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

    delivery_contract = relay_helpers._load_runtime_delivery_contract(
        attempt.execution_metadata
    )
    if delivery_contract is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime delivery contract.",
        )
    if delivery_contract.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime delivery contract.",
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

    dispatch_envelope = relay_helpers._load_runtime_dispatch_envelope(
        attempt.execution_metadata
    )
    if dispatch_envelope is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a recorded runtime dispatch envelope.",
        )
    if dispatch_envelope.session_identifier != payload.session_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read does not match the recorded runtime dispatch envelope.",
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

    _validate_runtime_profile_read_context(
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

    if plan.intent != RuntimeIntentType.READ_PROFILE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read only supports read-profile commands.",
        )
    if command.command_template.category != CommandCategory.PROFILE_CAPTURE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read only supports profile-capture command categories.",
        )

    adapter_request = _build_runtime_profile_read_adapter_request(
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
    if not adapter.supports_profile_read(adapter_request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Adapter '{plan.adapter_key}' does not support the profile-read vertical slice.",
        )

    try:
        result = adapter.execute_profile_read(adapter_request)
    except (NotImplementedError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    try:
        digest = _project_capture_load_profile_execution_digest(result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    try:
        terminal_status = _project_capture_load_profile_terminal_status(result, digest)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    result = result.model_copy(
        update={
            "capture_load_profile_execution_digest": digest,
            "capture_load_profile_terminal_status": terminal_status,
        }
    )
    profile_read_payload = {"runtime_profile_read_execution": result.model_dump(mode="json")}
    digest_payload = {
        "runtime_capture_load_profile_execution_digest": digest.model_dump(mode="json")
    }
    terminal_status_payload = {
        "runtime_capture_load_profile_terminal_status": terminal_status.model_dump(
            mode="json"
        )
    }
    attempt.execution_metadata = merge_runtime_metadata(
        attempt.execution_metadata,
        profile_read_payload,
    )
    attempt.execution_metadata = merge_runtime_metadata(
        attempt.execution_metadata,
        digest_payload,
    )
    attempt.execution_metadata = merge_runtime_metadata(
        attempt.execution_metadata,
        terminal_status_payload,
    )
    command.result_summary = merge_runtime_metadata(command.result_summary, profile_read_payload)
    command.result_summary = merge_runtime_metadata(command.result_summary, digest_payload)
    command.result_summary = merge_runtime_metadata(
        command.result_summary,
        terminal_status_payload,
    )
    job_run.result_summary = merge_runtime_metadata(job_run.result_summary, profile_read_payload)
    job_run.result_summary = merge_runtime_metadata(job_run.result_summary, digest_payload)
    job_run.result_summary = merge_runtime_metadata(
        job_run.result_summary,
        terminal_status_payload,
    )
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(command)
    session.refresh(job_run)
    return RuntimeProfileReadExecutionResponse(
        result=result,
        job_run=serialize_job_run(job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _build_runtime_profile_read_adapter_request(
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
) -> RuntimeProfileReadAdapterRequest:
    return RuntimeProfileReadAdapterRequest(
        adapter_key=plan.adapter_key,
        protocol_family=plan.protocol_family,
        operation=RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE,
        command_category=plan.command.category,
        execution_context=plan.execution_context,
        target=plan.target,
        transport=plan.transport,
        security=plan.security,
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


def _validate_runtime_profile_read_context(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
) -> None:
    lease = relay_helpers._load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a runtime lease.",
        )
    if lease.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is owned by another executor.",
        )

    invocation = relay_helpers._load_runtime_execution_invocation(execution_metadata)
    if invocation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime profile read requires a runtime invocation gate.",
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
            detail="Runtime profile read requires a runtime execution guard.",
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


def _load_runtime_profile_read_execution(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProfileReadExecutionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_profile_read_execution")
    if not isinstance(payload, dict):
        return None
    return RuntimeProfileReadExecutionResult.model_validate(payload)


def _load_runtime_capture_load_profile_execution_digest(
    execution_metadata: dict[str, object] | None,
) -> RuntimeCaptureLoadProfileExecutionDigest | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_capture_load_profile_execution_digest")
    if not isinstance(payload, dict):
        return None
    return RuntimeCaptureLoadProfileExecutionDigest.model_validate(payload)


def _load_runtime_capture_load_profile_terminal_status(
    execution_metadata: dict[str, object] | None,
) -> RuntimeCaptureLoadProfileTerminalStatus | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_capture_load_profile_terminal_status")
    if not isinstance(payload, dict):
        return None
    return RuntimeCaptureLoadProfileTerminalStatus.model_validate(payload)


def _project_capture_load_profile_execution_digest(
    result: RuntimeProfileReadExecutionResult,
) -> RuntimeCaptureLoadProfileExecutionDigest:
    if result.profile_read_operation != RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE:
        raise ValueError(
            "Runtime profile-read digest projector only supports the capture-load-profile slice."
        )

    adapter_summary = result.adapter_result_summary
    if not isinstance(adapter_summary, dict):
        raise ValueError(
            "Missing staged profile-read adapter artifacts for the capture-load-profile digest projector."
        )
    operation = adapter_summary.get("gurux_profile_read_operation")
    validated_target = adapter_summary.get("gurux_profile_read_validated_target")
    normalized_request = adapter_summary.get("gurux_profile_read_normalized_request")
    invocation_result = adapter_summary.get("gurux_profile_read_invocation_result")
    interpreter = adapter_summary.get("gurux_profile_read_interpreter")
    if not all(isinstance(item, dict) for item in [operation, validated_target, normalized_request, invocation_result, interpreter]):
        raise ValueError(
            "Missing staged profile-read adapter artifacts for the capture-load-profile digest projector."
        )

    final_execution_category = RuntimeCaptureLoadProfileExecutionCategory.COMPLETED
    if result.adapter_acknowledgment_state.value == "rejected":
        final_execution_category = RuntimeCaptureLoadProfileExecutionCategory.REJECTED
    elif result.execution_outcome != RuntimeCommandOutcome.SUCCEEDED:
        final_execution_category = RuntimeCaptureLoadProfileExecutionCategory.FAILED

    batch = result.profile_read_batch
    interval_count = len(batch.load_profile_intervals) if batch is not None else 0
    channel_count = (
        len({str(interval.channel_id) for interval in batch.load_profile_intervals})
        if batch is not None
        else 0
    )
    return RuntimeCaptureLoadProfileExecutionDigest(
        profile_read_execution_record_id=result.profile_read_execution_record_id,
        profile_read_operation=result.profile_read_operation,
        command_attempt_id=result.command_attempt_id,
        adapter_key=result.adapter_key,
        protocol_family=result.protocol_family,
        resolved_operation_obis_code=str(operation["obis_code"]),
        validated_target_state="validated",
        normalized_request_present=True,
        invocation_request_present=True,
        invocation_result_category=str(invocation_result["invocation_status"]),
        interpreter_outcome=result.execution_outcome,
        final_execution_category=final_execution_category,
        load_profile_interval_count=interval_count,
        channel_count=channel_count,
        correlation_id=result.correlation_id,
        request_id=result.request_id,
        session_identifier=result.session_identifier,
        summary=(
            "Capture-load-profile digest projected the bounded staged adapter artifacts "
            "into one compact runtime-facing audit summary."
        ),
    )


def _project_capture_load_profile_terminal_status(
    result: RuntimeProfileReadExecutionResult,
    digest: RuntimeCaptureLoadProfileExecutionDigest,
) -> RuntimeCaptureLoadProfileTerminalStatus:
    if result.profile_read_operation != RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE:
        raise ValueError(
            "Runtime profile-read terminal-status projector only supports the capture-load-profile slice."
        )

    adapter_summary = result.adapter_result_summary
    if not isinstance(adapter_summary, dict):
        raise ValueError(
            "Missing staged profile-read adapter artifacts for the capture-load-profile terminal-status projector."
        )
    operation = adapter_summary.get("gurux_profile_read_operation")
    validated_target = adapter_summary.get("gurux_profile_read_validated_target")
    normalized_request = adapter_summary.get("gurux_profile_read_normalized_request")
    invocation_result = adapter_summary.get("gurux_profile_read_invocation_result")
    interpreter = adapter_summary.get("gurux_profile_read_interpreter")

    if not isinstance(operation, dict) or not isinstance(validated_target, dict):
        terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.BLOCKED_PRE_INVOCATION
        invocation_result_category = None
    elif not isinstance(normalized_request, dict):
        terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.BLOCKED_PRE_INVOCATION
        invocation_result_category = None
    elif not isinstance(invocation_result, dict):
        terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.BLOCKED_MID_PIPELINE
        invocation_result_category = None
    else:
        invocation_result_category = str(invocation_result.get("invocation_status"))
        if invocation_result_category == "unavailable":
            terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.UNAVAILABLE
        elif not isinstance(interpreter, dict):
            terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.UNUSABLE_RESPONSE
        elif result.adapter_acknowledgment_state.value == "rejected":
            terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.REJECTED
        elif digest.final_execution_category == RuntimeCaptureLoadProfileExecutionCategory.COMPLETED:
            terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.ACKNOWLEDGED
        elif result.profile_read_batch is None:
            terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.UNUSABLE_RESPONSE
        else:
            terminal_status = RuntimeCaptureLoadProfileTerminalStatusCategory.BLOCKED_MID_PIPELINE

    return RuntimeCaptureLoadProfileTerminalStatus(
        profile_read_execution_record_id=result.profile_read_execution_record_id,
        profile_read_operation=result.profile_read_operation,
        command_attempt_id=result.command_attempt_id,
        adapter_key=result.adapter_key,
        protocol_family=result.protocol_family,
        terminal_status=terminal_status,
        invocation_result_category=invocation_result_category,
        digest_execution_category=digest.final_execution_category,
        interpreter_outcome=result.execution_outcome,
        correlation_id=result.correlation_id,
        request_id=result.request_id,
        session_identifier=result.session_identifier,
        summary=(
            "Capture-load-profile terminal status projected the bounded staged artifacts "
            "and digest into one compact runtime-facing terminal classification."
        ),
    )
