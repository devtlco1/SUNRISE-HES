import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.jobs.dependencies import require_internal_api_token
from app.runtime.contracts import (
    DerivedWorkCoordinationCategory,
    DerivedWorkDispatchCategory,
    DerivedWorkPickupCategory,
    PlatformReadinessDeltaStatus,
    PlatformReadinessHistoryEventKind,
    PlatformReadinessStatus,
    ProtocolExecutionPlan,
)
from app.runtime.schemas import (
    ConsumeDerivedWorkResponse,
    DatabaseReadinessDetailResponse,
    DerivedWorkCoordinationResponse,
    DerivedWorkDispatchRequestResponse,
    DerivedWorkPickupResponse,
    ExecuteRuntimePlanRequest,
    ExecuteRuntimePlanResponse,
    HandleDerivedWorkResponse,
    MaterializeFollowUpActionsResponse,
    PlatformCurrentReadinessResponse,
    PlatformReadinessComparisonResponse,
    PlatformReadinessHistoryResponse,
    PlatformStartupReadinessResponse,
    QueueAdaptersResponse,
    QueueEnqueueResponse,
    RedisConsumerGroupBootstrapRequest,
    RedisConsumerGroupBootstrapResponse,
    RedisConsumerGroupResetRequest,
    RedisConsumerGroupResetResponse,
    RedisDispatchAckRequest,
    RedisDispatchAckResponse,
    RedisDispatchDequeueClaimRequest,
    RedisDispatchDequeueClaimResponse,
    RedisDispatchPendingInspectionRequest,
    RedisDispatchPendingInspectionResponse,
    RedisDispatchRecoveryRequest,
    RedisDispatchRecoveryResponse,
    RedisDispatchReleaseRequest,
    RedisDispatchReleaseResponse,
    RedisDispatchRuntimeHandoffRequest,
    RedisTransportConfigResponse,
    RedisTransportReadinessResponse,
    RedisTransportStatusRequest,
    RedisTransportStatusResponse,
    RuntimeExecutionHandoffResponse,
    RuntimeExecutionInvocationGateRequest,
    RuntimeExecutionInvocationGateResponse,
    RuntimeExecutionLeaseRequest,
    RuntimeExecutionLeaseResponse,
    RuntimeAttemptDispositionBridgeRequest,
    RuntimeAttemptDispositionBridgeResponse,
    RuntimeExecutionOutcomeCheckpointRequest,
    RuntimeExecutionOutcomeCheckpointResponse,
    RuntimeFollowUpMaterializationBridgeRequest,
    RuntimeFollowUpMaterializationBridgeResponse,
    RuntimeOperationalClosureBridgeRequest,
    RuntimeOperationalClosureBridgeResponse,
    RuntimeProtocolExecutionIntentBridgeRequest,
    RuntimeProtocolExecutionIntentBridgeResponse,
    RuntimeProtocolAdapterSelectionBridgeRequest,
    RuntimeProtocolAdapterSelectionBridgeResponse,
    RuntimeProtocolDispatchRequestBridgeRequest,
    RuntimeProtocolDispatchRequestBridgeResponse,
    RuntimeProtocolExecutionObservationBridgeRequest,
    RuntimeProtocolExecutionObservationBridgeResponse,
    RuntimeProtocolInterpretationBridgeRequest,
    RuntimeProtocolInterpretationBridgeResponse,
    RuntimeProtocolReconciliationBridgeRequest,
    RuntimeProtocolReconciliationBridgeResponse,
    RuntimeTerminalSettlementBridgeRequest,
    RuntimeTerminalSettlementBridgeResponse,
    RuntimeClosureAttestationBridgeRequest,
    RuntimeClosureAttestationBridgeResponse,
    RuntimePublicationContractBridgeRequest,
    RuntimePublicationContractBridgeResponse,
    RuntimeExternalizationEnvelopeBridgeRequest,
    RuntimeExternalizationEnvelopeBridgeResponse,
    RuntimeDeliveryContractBridgeRequest,
    RuntimeDeliveryContractBridgeResponse,
    RuntimeDispatchEnvelopeBridgeRequest,
    RuntimeDispatchEnvelopeBridgeResponse,
    RuntimeOnDemandReadExecutionRequest,
    RuntimeOnDemandReadExecutionResponse,
    RuntimeTcpMeterIngressBindRequest,
    RuntimeTcpMeterIngressBindResponse,
    RuntimeTcpMeterIngressIdentityDiscoveryRequest,
    RuntimeTcpMeterIngressIdentityDiscoveryResponse,
    RuntimeTcpMeterIngressPersistDiscoveredMeterRequest,
    RuntimeTcpMeterIngressPersistDiscoveredMeterResponse,
    RuntimeTcpMeterIngressStatusResponse,
    RuntimeProfileReadExecutionRequest,
    RuntimeProfileReadExecutionResponse,
    RuntimeRelayControlExecutionRequest,
    RuntimeRelayControlExecutionResponse,
    RuntimeProtocolInvocationResultBridgeRequest,
    RuntimeProtocolInvocationResultBridgeResponse,
    RuntimePostProcessingBridgeRequest,
    RuntimePostProcessingBridgeResponse,
    RuntimeExecutionSessionFinalizeRequest,
    RuntimeExecutionSessionFinalizeResponse,
    RuntimeExecutionSessionHeartbeatRequest,
    RuntimeExecutionSessionResponse,
    RuntimeExecutionSessionStartRequest,
)
from app.runtime.services import (
    ack_redis_dispatch_message,
    bridge_runtime_disposition_to_post_processing,
    bridge_runtime_post_processing_to_follow_up_materialization,
    bridge_runtime_follow_up_materialization_to_operational_closure,
    bridge_runtime_operational_closure_to_protocol_execution_intent,
    bridge_runtime_protocol_execution_intent_to_adapter_selection,
    bridge_runtime_protocol_adapter_selection_to_dispatch_request,
    bridge_runtime_protocol_dispatch_request_to_invocation_result,
    bridge_runtime_protocol_invocation_result_to_execution_observation,
    bridge_runtime_protocol_execution_observation_to_interpretation,
    bridge_runtime_protocol_interpretation_to_reconciliation,
    bridge_runtime_protocol_reconciliation_to_terminal_settlement,
    bridge_runtime_terminal_settlement_to_closure_attestation,
    bridge_runtime_closure_attestation_to_publication_contract,
    bridge_runtime_publication_contract_to_externalization_envelope,
    bridge_runtime_externalization_envelope_to_delivery_contract,
    bridge_runtime_delivery_contract_to_dispatch_envelope,
    execute_runtime_on_demand_read_adapter,
    execute_runtime_profile_read_adapter,
    execute_runtime_relay_control_adapter,
    bootstrap_redis_consumer_group,
    bind_runtime_tcp_meter_ingress_connection,
    bridge_runtime_execution_outcome_to_attempt_disposition,
    build_runtime_plan_for_command,
    consume_derived_work_job_run,
    dequeue_and_claim_redis_dispatch_message,
    discover_runtime_tcp_meter_identity,
    enqueue_dispatch_request_for_job_run,
    evaluate_redis_transport_readiness,
    execute_runtime_plan_for_attempt,
    finalize_runtime_execution_session,
    gate_runtime_execution_invocation,
    get_database_readiness_detail,
    get_database_startup_readiness_snapshot,
    get_effective_redis_transport_config,
    get_platform_current_readiness,
    get_platform_readiness_comparison,
    get_platform_readiness_history,
    get_platform_startup_readiness,
    get_runtime_tcp_meter_ingress_status,
    get_redis_transport_status,
    handle_derived_work_job_run,
    handoff_claimed_redis_dispatch_message_to_runtime,
    inspect_pending_redis_dispatch_messages,
    lease_runtime_execution_work_item,
    list_derived_work_dispatch_requests,
    list_derived_work_for_pickup,
    list_dispatch_ready_derived_work,
    list_queue_adapters,
    materialize_follow_up_actions_for_attempt,
    persist_runtime_tcp_meter_discovered_identity,
    record_runtime_execution_outcome,
    record_platform_current_readiness_event,
    record_platform_readiness_comparison_event,
    recover_stale_redis_dispatch_message,
    release_redis_dispatch_message,
    reset_redis_consumer_group,
    heartbeat_runtime_execution_session,
    start_runtime_execution_session,
    unbind_runtime_tcp_meter_ingress_connection,
)

internal_runtime_router = APIRouter(prefix="/internal/commands", tags=["internal-runtime"])
internal_runtime_attempts_router = APIRouter(
    prefix="/internal/command-attempts",
    tags=["internal-runtime-attempts"],
)
internal_runtime_job_runs_router = APIRouter(
    prefix="/internal/job-runs",
    tags=["internal-runtime-job-runs"],
)
internal_runtime_queue_router = APIRouter(
    prefix="/internal/queue",
    tags=["internal-runtime-queue"],
)
internal_runtime_platform_router = APIRouter(
    prefix="/internal/platform",
    tags=["internal-runtime-platform"],
)


@internal_runtime_router.post(
    "/{command_id}/build-runtime-plan",
    response_model=ProtocolExecutionPlan,
    dependencies=[Depends(require_internal_api_token)],
)
def build_runtime_plan_endpoint(
    command_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_db_session),
) -> ProtocolExecutionPlan:
    request_context = getattr(request.state, "request_audit_context", None)
    request_id = getattr(request_context, "request_id", None)
    return build_runtime_plan_for_command(
        session,
        command_id=command_id,
        request_id=request_id,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/start-execution-session",
    response_model=RuntimeExecutionSessionResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def start_runtime_execution_session_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionSessionStartRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExecutionSessionResponse:
    return start_runtime_execution_session(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/heartbeat-execution-session",
    response_model=RuntimeExecutionSessionResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def heartbeat_runtime_execution_session_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionSessionHeartbeatRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExecutionSessionResponse:
    return heartbeat_runtime_execution_session(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/execute-on-demand-read-adapter",
    response_model=RuntimeOnDemandReadExecutionResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def execute_runtime_on_demand_read_adapter_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeOnDemandReadExecutionRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeOnDemandReadExecutionResponse:
    return execute_runtime_on_demand_read_adapter(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/execute-profile-read-adapter",
    response_model=RuntimeProfileReadExecutionResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def execute_runtime_profile_read_adapter_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProfileReadExecutionRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProfileReadExecutionResponse:
    return execute_runtime_profile_read_adapter(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/execute-relay-control-adapter",
    response_model=RuntimeRelayControlExecutionResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def execute_runtime_relay_control_adapter_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeRelayControlExecutionRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeRelayControlExecutionResponse:
    return execute_runtime_relay_control_adapter(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-delivery-contract-to-dispatch-envelope",
    response_model=RuntimeDispatchEnvelopeBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_delivery_contract_to_dispatch_envelope_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeDispatchEnvelopeBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeDispatchEnvelopeBridgeResponse:
    return bridge_runtime_delivery_contract_to_dispatch_envelope(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-externalization-envelope-to-delivery-contract",
    response_model=RuntimeDeliveryContractBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_externalization_envelope_to_delivery_contract_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeDeliveryContractBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeDeliveryContractBridgeResponse:
    return bridge_runtime_externalization_envelope_to_delivery_contract(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-publication-contract-to-externalization-envelope",
    response_model=RuntimeExternalizationEnvelopeBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_publication_contract_to_externalization_envelope_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeExternalizationEnvelopeBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExternalizationEnvelopeBridgeResponse:
    return bridge_runtime_publication_contract_to_externalization_envelope(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-closure-attestation-to-publication-contract",
    response_model=RuntimePublicationContractBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_closure_attestation_to_publication_contract_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimePublicationContractBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimePublicationContractBridgeResponse:
    return bridge_runtime_closure_attestation_to_publication_contract(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-terminal-settlement-to-closure-attestation",
    response_model=RuntimeClosureAttestationBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_terminal_settlement_to_closure_attestation_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeClosureAttestationBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeClosureAttestationBridgeResponse:
    return bridge_runtime_terminal_settlement_to_closure_attestation(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-protocol-reconciliation-to-terminal-settlement",
    response_model=RuntimeTerminalSettlementBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_protocol_reconciliation_to_terminal_settlement_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeTerminalSettlementBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeTerminalSettlementBridgeResponse:
    return bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-protocol-interpretation-to-reconciliation",
    response_model=RuntimeProtocolReconciliationBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_protocol_interpretation_to_reconciliation_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolReconciliationBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProtocolReconciliationBridgeResponse:
    return bridge_runtime_protocol_interpretation_to_reconciliation(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-protocol-execution-observation-to-interpretation",
    response_model=RuntimeProtocolInterpretationBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_protocol_execution_observation_to_interpretation_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolInterpretationBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProtocolInterpretationBridgeResponse:
    return bridge_runtime_protocol_execution_observation_to_interpretation(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-protocol-invocation-result-to-execution-observation",
    response_model=RuntimeProtocolExecutionObservationBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_protocol_invocation_result_to_execution_observation_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolExecutionObservationBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProtocolExecutionObservationBridgeResponse:
    return bridge_runtime_protocol_invocation_result_to_execution_observation(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-protocol-dispatch-request-to-invocation-result",
    response_model=RuntimeProtocolInvocationResultBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_protocol_dispatch_request_to_invocation_result_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolInvocationResultBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProtocolInvocationResultBridgeResponse:
    return bridge_runtime_protocol_dispatch_request_to_invocation_result(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-protocol-adapter-selection-to-dispatch-request",
    response_model=RuntimeProtocolDispatchRequestBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_protocol_adapter_selection_to_dispatch_request_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolDispatchRequestBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProtocolDispatchRequestBridgeResponse:
    return bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-protocol-execution-intent-to-adapter-selection",
    response_model=RuntimeProtocolAdapterSelectionBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_protocol_execution_intent_to_adapter_selection_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolAdapterSelectionBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProtocolAdapterSelectionBridgeResponse:
    return bridge_runtime_protocol_execution_intent_to_adapter_selection(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-operational-closure-to-protocol-execution-intent",
    response_model=RuntimeProtocolExecutionIntentBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_operational_closure_to_protocol_execution_intent_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeProtocolExecutionIntentBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeProtocolExecutionIntentBridgeResponse:
    return bridge_runtime_operational_closure_to_protocol_execution_intent(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-follow-up-materialization-to-operational-closure",
    response_model=RuntimeOperationalClosureBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_follow_up_materialization_to_operational_closure_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeOperationalClosureBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeOperationalClosureBridgeResponse:
    return bridge_runtime_follow_up_materialization_to_operational_closure(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-post-processing-to-follow-up-materialization",
    response_model=RuntimeFollowUpMaterializationBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_post_processing_to_follow_up_materialization_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeFollowUpMaterializationBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeFollowUpMaterializationBridgeResponse:
    return bridge_runtime_post_processing_to_follow_up_materialization(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-attempt-disposition-to-post-processing",
    response_model=RuntimePostProcessingBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_disposition_to_post_processing_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimePostProcessingBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimePostProcessingBridgeResponse:
    return bridge_runtime_disposition_to_post_processing(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/bridge-execution-outcome-to-attempt",
    response_model=RuntimeAttemptDispositionBridgeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bridge_runtime_execution_outcome_to_attempt_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeAttemptDispositionBridgeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeAttemptDispositionBridgeResponse:
    return bridge_runtime_execution_outcome_to_attempt_disposition(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/record-execution-outcome",
    response_model=RuntimeExecutionOutcomeCheckpointResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def record_runtime_execution_outcome_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionOutcomeCheckpointRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExecutionOutcomeCheckpointResponse:
    return record_runtime_execution_outcome(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/finalize-execution-session",
    response_model=RuntimeExecutionSessionFinalizeResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def finalize_runtime_execution_session_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionSessionFinalizeRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExecutionSessionFinalizeResponse:
    return finalize_runtime_execution_session(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/gate-execution-invocation",
    response_model=RuntimeExecutionInvocationGateResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def gate_runtime_execution_invocation_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionInvocationGateRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExecutionInvocationGateResponse:
    return gate_runtime_execution_invocation(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/lease-execution",
    response_model=RuntimeExecutionLeaseResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def lease_runtime_execution_endpoint(
    attempt_id: uuid.UUID,
    payload: RuntimeExecutionLeaseRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExecutionLeaseResponse:
    return lease_runtime_execution_work_item(
        session,
        attempt_id=attempt_id,
        payload=payload,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/execute-runtime-plan",
    response_model=ExecuteRuntimePlanResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def execute_runtime_plan_endpoint(
    attempt_id: uuid.UUID,
    payload: ExecuteRuntimePlanRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> ExecuteRuntimePlanResponse:
    request_context = getattr(request.state, "request_audit_context", None)
    request_id = getattr(request_context, "request_id", None)
    return execute_runtime_plan_for_attempt(
        session,
        attempt_id=attempt_id,
        worker_identifier=payload.worker_identifier,
        request_id=request_id,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/materialize-follow-up-actions",
    response_model=MaterializeFollowUpActionsResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def materialize_follow_up_actions_endpoint(
    attempt_id: uuid.UUID,
    session: Session = Depends(get_db_session),
) -> MaterializeFollowUpActionsResponse:
    return materialize_follow_up_actions_for_attempt(session, attempt_id=attempt_id)


@internal_runtime_job_runs_router.post(
    "/{job_run_id}/consume-derived-work",
    response_model=ConsumeDerivedWorkResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def consume_derived_work_endpoint(
    job_run_id: uuid.UUID,
    session: Session = Depends(get_db_session),
) -> ConsumeDerivedWorkResponse:
    return consume_derived_work_job_run(session, job_run_id=job_run_id)


@internal_runtime_job_runs_router.get(
    "/derived-work-pickup",
    response_model=DerivedWorkPickupResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def list_derived_work_pickup_endpoint(
    pickup_category: DerivedWorkPickupCategory | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> DerivedWorkPickupResponse:
    return list_derived_work_for_pickup(session, pickup_category=pickup_category, limit=limit)


@internal_runtime_job_runs_router.get(
    "/dispatch-ready-derived-work",
    response_model=DerivedWorkCoordinationResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def list_dispatch_ready_derived_work_endpoint(
    coordination_category: DerivedWorkCoordinationCategory | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> DerivedWorkCoordinationResponse:
    return list_dispatch_ready_derived_work(
        session,
        coordination_category=coordination_category,
        limit=limit,
    )


@internal_runtime_job_runs_router.get(
    "/dispatch-requests",
    response_model=DerivedWorkDispatchRequestResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def list_dispatch_requests_endpoint(
    dispatch_category: DerivedWorkDispatchCategory | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> DerivedWorkDispatchRequestResponse:
    return list_derived_work_dispatch_requests(
        session,
        dispatch_category=dispatch_category,
        limit=limit,
    )


@internal_runtime_job_runs_router.post(
    "/{job_run_id}/enqueue-dispatch-request",
    response_model=QueueEnqueueResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def enqueue_dispatch_request_endpoint(
    job_run_id: uuid.UUID,
    session: Session = Depends(get_db_session),
) -> QueueEnqueueResponse:
    return enqueue_dispatch_request_for_job_run(session, job_run_id=job_run_id)


@internal_runtime_queue_router.get(
    "/adapters",
    response_model=QueueAdaptersResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def list_queue_adapters_endpoint() -> QueueAdaptersResponse:
    return list_queue_adapters()


@internal_runtime_queue_router.get(
    "/transport-config",
    response_model=RedisTransportConfigResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_transport_config_endpoint() -> RedisTransportConfigResponse:
    return RedisTransportConfigResponse(result=get_effective_redis_transport_config())


@internal_runtime_queue_router.get(
    "/transport-readiness",
    response_model=RedisTransportReadinessResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_transport_readiness_endpoint() -> RedisTransportReadinessResponse:
    return RedisTransportReadinessResponse(
        result=evaluate_redis_transport_readiness(apply_startup_policy=False)
    )


def _serialize_runtime_tcp_meter_ingress_status() -> RuntimeTcpMeterIngressStatusResponse:
    snapshot = get_runtime_tcp_meter_ingress_status()
    return RuntimeTcpMeterIngressStatusResponse(
        result={
            "listener_enabled": snapshot.listener_enabled,
            "listen_host": snapshot.listen_host,
            "listen_port": snapshot.listen_port,
            "listening": snapshot.listening,
            "connected": snapshot.connected,
            "active_connection_id": snapshot.active_connection_id,
            "remote_addr": snapshot.remote_addr,
            "remote_port": snapshot.remote_port,
            "connected_at": snapshot.connected_at.isoformat()
            if snapshot.connected_at is not None
            else None,
            "bound_meter_id": snapshot.bound_meter_id,
            "bound_endpoint_id": snapshot.bound_endpoint_id,
            "bound_protocol_association_profile_id": (
                snapshot.bound_protocol_association_profile_id
            ),
            "bound_at": snapshot.bound_at.isoformat() if snapshot.bound_at is not None else None,
            "connection_in_use": snapshot.connection_in_use,
        }
    )


@internal_runtime_platform_router.get(
    "/database-readiness",
    response_model=DatabaseReadinessDetailResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_database_readiness_endpoint() -> DatabaseReadinessDetailResponse:
    return DatabaseReadinessDetailResponse(result=get_database_readiness_detail())


@internal_runtime_platform_router.get(
    "/database-startup-readiness",
    response_model=DatabaseReadinessDetailResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_database_startup_readiness_endpoint(
    request: Request,
) -> DatabaseReadinessDetailResponse:
    return DatabaseReadinessDetailResponse(
        result=get_database_startup_readiness_snapshot(request.app)
    )


@internal_runtime_platform_router.get(
    "/readiness-comparison",
    response_model=PlatformReadinessComparisonResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_platform_readiness_comparison_endpoint(
    request: Request,
) -> PlatformReadinessComparisonResponse:
    result = get_platform_readiness_comparison(request.app)
    record_platform_readiness_comparison_event(request.app, result)
    return PlatformReadinessComparisonResponse(result=result)


@internal_runtime_platform_router.get(
    "/readiness-history",
    response_model=PlatformReadinessHistoryResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_platform_readiness_history_endpoint(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    recorded_after: datetime | None = Query(default=None),
    recorded_before: datetime | None = Query(default=None),
    event_kind: PlatformReadinessHistoryEventKind | None = Query(default=None),
    status: PlatformReadinessStatus | None = Query(default=None),
    delta_status: PlatformReadinessDeltaStatus | None = Query(default=None),
    component_name: str | None = Query(default=None),
    component_delta_status: PlatformReadinessDeltaStatus | None = Query(default=None),
    component_status: PlatformReadinessStatus | None = Query(default=None),
    component_ready: bool | None = Query(default=None),
) -> PlatformReadinessHistoryResponse:
    return PlatformReadinessHistoryResponse(
        result=get_platform_readiness_history(
            request.app,
            limit=limit,
            recorded_after=recorded_after,
            recorded_before=recorded_before,
            event_kind=event_kind,
            status=status,
            delta_status=delta_status,
            component_name=component_name,
            component_delta_status=component_delta_status,
            component_status=component_status,
            component_ready=component_ready,
        )
    )


@internal_runtime_platform_router.get(
    "/current-readiness",
    response_model=PlatformCurrentReadinessResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_platform_current_readiness_endpoint(
    request: Request,
) -> PlatformCurrentReadinessResponse:
    result = get_platform_current_readiness()
    record_platform_current_readiness_event(request.app, result)
    return PlatformCurrentReadinessResponse(result=result)


@internal_runtime_platform_router.get(
    "/startup-readiness",
    response_model=PlatformStartupReadinessResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_platform_startup_readiness_endpoint(
    request: Request,
) -> PlatformStartupReadinessResponse:
    return PlatformStartupReadinessResponse(result=get_platform_startup_readiness(request.app))


@internal_runtime_platform_router.get(
    "/tcp-meter-ingress/status",
    response_model=RuntimeTcpMeterIngressStatusResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_runtime_tcp_meter_ingress_status_endpoint() -> RuntimeTcpMeterIngressStatusResponse:
    return _serialize_runtime_tcp_meter_ingress_status()


@internal_runtime_platform_router.post(
    "/tcp-meter-ingress/bind-active-connection",
    response_model=RuntimeTcpMeterIngressBindResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bind_runtime_tcp_meter_ingress_connection_endpoint(
    payload: RuntimeTcpMeterIngressBindRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeTcpMeterIngressBindResponse:
    bind_runtime_tcp_meter_ingress_connection(
        session,
        meter_id=payload.meter_id,
        endpoint_id=payload.endpoint_id,
        protocol_association_profile_id=payload.protocol_association_profile_id,
    )
    return RuntimeTcpMeterIngressBindResponse(result=_serialize_runtime_tcp_meter_ingress_status().result)


@internal_runtime_platform_router.post(
    "/tcp-meter-ingress/unbind-active-connection",
    response_model=RuntimeTcpMeterIngressBindResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def unbind_runtime_tcp_meter_ingress_connection_endpoint() -> RuntimeTcpMeterIngressBindResponse:
    unbind_runtime_tcp_meter_ingress_connection()
    return RuntimeTcpMeterIngressBindResponse(result=_serialize_runtime_tcp_meter_ingress_status().result)


@internal_runtime_platform_router.post(
    "/tcp-meter-ingress/discover-identity",
    response_model=RuntimeTcpMeterIngressIdentityDiscoveryResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def discover_runtime_tcp_meter_identity_endpoint(
    payload: RuntimeTcpMeterIngressIdentityDiscoveryRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeTcpMeterIngressIdentityDiscoveryResponse:
    result = discover_runtime_tcp_meter_identity(
        session,
        protocol_association_profile_id=payload.protocol_association_profile_id,
    )
    return RuntimeTcpMeterIngressIdentityDiscoveryResponse(
        result={
            "success": result.success,
            "active_connection_id": result.active_connection_id,
            "protocol_association_profile_id": result.protocol_association_profile_id,
            "discovered_identity_value": result.discovered_identity_value,
            "discovered_identity_obis_code": result.discovered_identity_obis_code,
            "identity_values": result.identity_values,
            "protocol_path_used": result.protocol_path_used,
            "diagnostic_message": result.diagnostic_message,
            "remote_addr": result.remote_addr,
            "remote_port": result.remote_port,
        }
    )


@internal_runtime_platform_router.post(
    "/tcp-meter-ingress/persist-discovered-meter",
    response_model=RuntimeTcpMeterIngressPersistDiscoveredMeterResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def persist_runtime_tcp_meter_discovered_identity_endpoint(
    payload: RuntimeTcpMeterIngressPersistDiscoveredMeterRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeTcpMeterIngressPersistDiscoveredMeterResponse:
    result = persist_runtime_tcp_meter_discovered_identity(
        session,
        protocol_association_profile_id=payload.protocol_association_profile_id,
    )
    return RuntimeTcpMeterIngressPersistDiscoveredMeterResponse(
        result={
            "success": result.success,
            "active_connection_id": result.active_connection_id,
            "protocol_association_profile_id": result.protocol_association_profile_id,
            "discovered_identity_value": result.discovered_identity_value,
            "discovered_identity_obis_code": result.discovered_identity_obis_code,
            "matched_existing_meter": result.matched_existing_meter,
            "meter_id": result.meter_id,
            "communication_endpoint_id": result.communication_endpoint_id,
            "assignment_id": result.assignment_id,
            "created_meter": result.created_meter,
            "created_endpoint": result.created_endpoint,
            "created_assignment": result.created_assignment,
            "diagnostic_message": result.diagnostic_message,
        }
    )


@internal_runtime_queue_router.post(
    "/transport-admin/bootstrap-consumer-group",
    response_model=RedisConsumerGroupBootstrapResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bootstrap_consumer_group_endpoint(
    payload: RedisConsumerGroupBootstrapRequest,
) -> RedisConsumerGroupBootstrapResponse:
    return RedisConsumerGroupBootstrapResponse(result=bootstrap_redis_consumer_group(payload))


@internal_runtime_queue_router.post(
    "/transport-admin/reset-consumer-group",
    response_model=RedisConsumerGroupResetResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def reset_consumer_group_endpoint(
    payload: RedisConsumerGroupResetRequest,
) -> RedisConsumerGroupResetResponse:
    return RedisConsumerGroupResetResponse(result=reset_redis_consumer_group(payload))


@internal_runtime_queue_router.post(
    "/dispatch-messages/dequeue-claim",
    response_model=RedisDispatchDequeueClaimResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def dequeue_claim_dispatch_message_endpoint(
    payload: RedisDispatchDequeueClaimRequest,
) -> RedisDispatchDequeueClaimResponse:
    return RedisDispatchDequeueClaimResponse(
        result=dequeue_and_claim_redis_dispatch_message(payload)
    )


@internal_runtime_queue_router.post(
    "/dispatch-messages/runtime-handoff",
    response_model=RuntimeExecutionHandoffResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def runtime_handoff_dispatch_message_endpoint(
    payload: RedisDispatchRuntimeHandoffRequest,
    session: Session = Depends(get_db_session),
) -> RuntimeExecutionHandoffResponse:
    return handoff_claimed_redis_dispatch_message_to_runtime(
        session,
        payload=payload,
    )


@internal_runtime_queue_router.post(
    "/dispatch-messages/ack",
    response_model=RedisDispatchAckResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def ack_dispatch_message_endpoint(
    payload: RedisDispatchAckRequest,
) -> RedisDispatchAckResponse:
    return RedisDispatchAckResponse(result=ack_redis_dispatch_message(payload))


@internal_runtime_queue_router.post(
    "/dispatch-messages/release",
    response_model=RedisDispatchReleaseResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def release_dispatch_message_endpoint(
    payload: RedisDispatchReleaseRequest,
) -> RedisDispatchReleaseResponse:
    return RedisDispatchReleaseResponse(result=release_redis_dispatch_message(payload))


@internal_runtime_queue_router.post(
    "/dispatch-messages/pending-inspection",
    response_model=RedisDispatchPendingInspectionResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def inspect_pending_dispatch_messages_endpoint(
    payload: RedisDispatchPendingInspectionRequest,
) -> RedisDispatchPendingInspectionResponse:
    return RedisDispatchPendingInspectionResponse(
        result=inspect_pending_redis_dispatch_messages(payload)
    )


@internal_runtime_queue_router.post(
    "/dispatch-messages/recover",
    response_model=RedisDispatchRecoveryResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def recover_dispatch_message_endpoint(
    payload: RedisDispatchRecoveryRequest,
) -> RedisDispatchRecoveryResponse:
    return RedisDispatchRecoveryResponse(result=recover_stale_redis_dispatch_message(payload))


@internal_runtime_queue_router.post(
    "/transport-status",
    response_model=RedisTransportStatusResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def get_transport_status_endpoint(
    payload: RedisTransportStatusRequest,
) -> RedisTransportStatusResponse:
    return RedisTransportStatusResponse(result=get_redis_transport_status(payload))


@internal_runtime_job_runs_router.post(
    "/{job_run_id}/handle-derived-work",
    response_model=HandleDerivedWorkResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def handle_derived_work_endpoint(
    job_run_id: uuid.UUID,
    session: Session = Depends(get_db_session),
) -> HandleDerivedWorkResponse:
    return handle_derived_work_job_run(session, job_run_id=job_run_id)
