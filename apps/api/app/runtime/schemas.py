from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.commands.schemas import CommandExecutionAttemptResponse, MeterCommandResponse
from app.modules.connectivity.schemas import ConnectivitySessionHistoryResponse
from app.modules.events.schemas import MeterEventIngestionResponse
from app.modules.jobs.schemas import JobRunResponse
from app.modules.readings.schemas import MeterReadingBatchResponse
from app.runtime.contracts import (
    DatabaseReadinessDetailResult,
    DerivedWorkCoordinationCategory,
    DerivedWorkDispatchCategory,
    DerivedWorkHandlerCategory,
    DerivedWorkHandlerResult,
    DerivedWorkLineage,
    DerivedWorkPickupCategory,
    DerivedWorkRoutingCategory,
    DerivedWorkRoutingResult,
    DownstreamFollowUpActionType,
    DownstreamSignalConsumptionResult,
    PlatformCurrentReadinessResult,
    PlatformReadinessComparisonResult,
    PlatformReadinessHistoryResult,
    PlatformStartupReadinessResult,
    ProtocolExecutionPlan,
    QueueAdapterCapabilities,
    QueueEnqueueResult,
    RedisDispatchAckResult,
    RedisDispatchClaimResult,
    RedisDispatchPendingInspectionResult,
    RedisDispatchRecoveryResult,
    RedisDispatchReleaseResult,
    RedisTransportAdminResult,
    RedisTransportConfigResult,
    RedisTransportReadinessResult,
    RedisTransportStatusResult,
    RuntimeAttemptDispositionResult,
    RuntimeCommandOutcome,
    RuntimeExecutionHandoffResult,
    RuntimeExecutionInvocationGateResult,
    RuntimeExecutionLeaseResult,
    RuntimeExecutionOutcomeResult,
    RuntimeFollowUpMaterializationResult,
    RuntimeOperationalClosureResult,
    RuntimeProtocolAdapterSelectionResult,
    RuntimeProtocolDispatchRequestResult,
    RuntimeProtocolExecutionObservationResult,
    RuntimeProtocolInterpretationResult,
    RuntimeProtocolReconciliationResult,
    RuntimeProtocolInvocationResult,
    RuntimeProtocolExecutionIntentResult,
    RuntimeTerminalSettlementResult,
    RuntimeClosureAttestationResult,
    RuntimePublicationContractResult,
    RuntimeExternalizationEnvelopeResult,
    RuntimeDeliveryContractResult,
    RuntimeDispatchEnvelopeResult,
    RuntimeRelayControlExecutionResult,
    RuntimePostProcessingBridgeResult,
    RuntimeExecutionSessionFinalizeResult,
    RuntimeExecutionSessionResult,
    RuntimePostProcessingResult,
)


class ExecuteRuntimePlanRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)


class FollowUpMaterializedRunResponse(BaseModel):
    action_type: DownstreamFollowUpActionType
    materialized: bool
    job_run: JobRunResponse


class MaterializeFollowUpActionsResponse(BaseModel):
    source_attempt_id: str
    materialized_count: int
    existing_count: int
    items: list[FollowUpMaterializedRunResponse]


class ConsumeDerivedWorkResponse(BaseModel):
    job_run: JobRunResponse
    routing: DerivedWorkRoutingResult


class DerivedWorkPickupProjection(BaseModel):
    job_run: JobRunResponse
    pickup_category: DerivedWorkPickupCategory
    routing_category: DerivedWorkRoutingCategory
    lineage: DerivedWorkLineage | None = None
    eligible_for_retry_pickup: bool
    eligible_for_followup_pickup: bool


class DerivedWorkPickupResponse(BaseModel):
    total: int
    retry_items: list[DerivedWorkPickupProjection] = Field(default_factory=list)
    followup_items: list[DerivedWorkPickupProjection] = Field(default_factory=list)


class HandleDerivedWorkResponse(BaseModel):
    job_run: JobRunResponse
    handler: DerivedWorkHandlerResult


class DerivedWorkCoordinationProjection(BaseModel):
    job_run: JobRunResponse
    coordination_category: DerivedWorkCoordinationCategory
    handler_category: DerivedWorkHandlerCategory
    lineage: DerivedWorkLineage | None = None
    dispatch_ready: bool


class DerivedWorkCoordinationResponse(BaseModel):
    total: int
    retry_items: list[DerivedWorkCoordinationProjection] = Field(default_factory=list)
    followup_items: list[DerivedWorkCoordinationProjection] = Field(default_factory=list)


class DerivedWorkDispatchRequestProjection(BaseModel):
    job_run: JobRunResponse
    dispatch_category: DerivedWorkDispatchCategory
    source_job_run_id: str
    lineage: DerivedWorkLineage | None = None
    derived_correlation_id: str | None = None
    dispatch_ready_metadata: dict[str, object]
    intended_path: str


class DerivedWorkDispatchRequestResponse(BaseModel):
    total: int
    retry_items: list[DerivedWorkDispatchRequestProjection] = Field(default_factory=list)
    followup_items: list[DerivedWorkDispatchRequestProjection] = Field(default_factory=list)


class QueueEnqueueResponse(BaseModel):
    job_run: JobRunResponse
    enqueue_result: QueueEnqueueResult


class QueueAdapterDescriptorResponse(BaseModel):
    code: str
    implementation: str
    is_default: bool
    capabilities: QueueAdapterCapabilities


class QueueAdaptersResponse(BaseModel):
    active_backend: str
    items: list[QueueAdapterDescriptorResponse]


class RedisDispatchDequeueClaimRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    block_ms: int = Field(default=0, ge=0, le=60000)
    ensure_consumer_group: bool = False


class RedisDispatchDequeueClaimResponse(BaseModel):
    result: RedisDispatchClaimResult


class RedisDispatchRuntimeHandoffRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    claim_token: str = Field(min_length=1, max_length=512)
    lease_seconds: int = Field(default=60, ge=5, le=3600)
    endpoint_id: UUID | None = None
    session_history_id: UUID | None = None
    request_snapshot: dict[str, object] | None = None
    execution_metadata: dict[str, object] | None = None


class RuntimeExecutionHandoffResponse(BaseModel):
    result: RuntimeExecutionHandoffResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeExecutionLeaseRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=60, ge=5, le=3600)


class RuntimeExecutionLeaseResponse(BaseModel):
    result: RuntimeExecutionLeaseResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeExecutionInvocationGateRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)


class RuntimeExecutionInvocationGateResponse(BaseModel):
    result: RuntimeExecutionInvocationGateResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeExecutionSessionStartRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_timeout_seconds: int = Field(default=60, ge=5, le=3600)


class RuntimeExecutionSessionHeartbeatRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    session_timeout_seconds: int = Field(default=60, ge=5, le=3600)


class RuntimeExecutionSessionFinalizeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    finalize_reason: str | None = Field(default=None, max_length=255)


class RuntimeExecutionSessionResponse(BaseModel):
    result: RuntimeExecutionSessionResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeExecutionSessionFinalizeResponse(BaseModel):
    result: RuntimeExecutionSessionFinalizeResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeExecutionOutcomeCheckpointRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    terminal_outcome: str = Field(min_length=1, max_length=64)
    outcome_reason: str | None = Field(default=None, max_length=255)
    summary_message: str | None = Field(default=None, max_length=512)


class RuntimeExecutionOutcomeCheckpointResponse(BaseModel):
    result: RuntimeExecutionOutcomeResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeAttemptDispositionBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    disposition_reason: str | None = Field(default=None, max_length=255)


class RuntimeAttemptDispositionBridgeResponse(BaseModel):
    result: RuntimeAttemptDispositionResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimePostProcessingBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    post_processing_reason: str | None = Field(default=None, max_length=255)


class RuntimePostProcessingBridgeResponse(BaseModel):
    result: RuntimePostProcessingBridgeResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeFollowUpMaterializationBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    materialization_reason: str | None = Field(default=None, max_length=255)


class RuntimeFollowUpMaterializationBridgeResponse(BaseModel):
    result: RuntimeFollowUpMaterializationResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeOperationalClosureBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    closure_reason: str | None = Field(default=None, max_length=255)


class RuntimeOperationalClosureBridgeResponse(BaseModel):
    result: RuntimeOperationalClosureResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeProtocolExecutionIntentBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    intent_reason: str | None = Field(default=None, max_length=255)


class RuntimeProtocolExecutionIntentBridgeResponse(BaseModel):
    result: RuntimeProtocolExecutionIntentResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeProtocolAdapterSelectionBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    selection_reason: str | None = Field(default=None, max_length=255)


class RuntimeProtocolAdapterSelectionBridgeResponse(BaseModel):
    result: RuntimeProtocolAdapterSelectionResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeProtocolDispatchRequestBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    request_reason: str | None = Field(default=None, max_length=255)


class RuntimeProtocolDispatchRequestBridgeResponse(BaseModel):
    result: RuntimeProtocolDispatchRequestResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeProtocolInvocationResultBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    result_reason: str | None = Field(default=None, max_length=255)


class RuntimeProtocolInvocationResultBridgeResponse(BaseModel):
    result: RuntimeProtocolInvocationResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeProtocolExecutionObservationBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    observation_reason: str | None = Field(default=None, max_length=255)


class RuntimeProtocolExecutionObservationBridgeResponse(BaseModel):
    result: RuntimeProtocolExecutionObservationResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeProtocolInterpretationBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    interpretation_reason: str | None = Field(default=None, max_length=255)


class RuntimeProtocolInterpretationBridgeResponse(BaseModel):
    result: RuntimeProtocolInterpretationResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeProtocolReconciliationBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    reconciliation_reason: str | None = Field(default=None, max_length=255)


class RuntimeProtocolReconciliationBridgeResponse(BaseModel):
    result: RuntimeProtocolReconciliationResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeTerminalSettlementBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    settlement_reason: str | None = Field(default=None, max_length=255)


class RuntimeTerminalSettlementBridgeResponse(BaseModel):
    result: RuntimeTerminalSettlementResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeClosureAttestationBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    attestation_reason: str | None = Field(default=None, max_length=255)


class RuntimeClosureAttestationBridgeResponse(BaseModel):
    result: RuntimeClosureAttestationResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimePublicationContractBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    publication_contract_reason: str | None = Field(default=None, max_length=255)


class RuntimePublicationContractBridgeResponse(BaseModel):
    result: RuntimePublicationContractResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeExternalizationEnvelopeBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    envelope_reason: str | None = Field(default=None, max_length=255)


class RuntimeExternalizationEnvelopeBridgeResponse(BaseModel):
    result: RuntimeExternalizationEnvelopeResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeDeliveryContractBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    delivery_contract_reason: str | None = Field(default=None, max_length=255)


class RuntimeDeliveryContractBridgeResponse(BaseModel):
    result: RuntimeDeliveryContractResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeDispatchEnvelopeBridgeRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    dispatch_envelope_reason: str | None = Field(default=None, max_length=255)


class RuntimeDispatchEnvelopeBridgeResponse(BaseModel):
    result: RuntimeDispatchEnvelopeResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RuntimeRelayControlExecutionRequest(BaseModel):
    executor_identifier: str = Field(min_length=1, max_length=128)
    session_identifier: str = Field(min_length=1, max_length=255)
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    execution_reason: str | None = Field(default=None, max_length=255)


class RuntimeRelayControlExecutionResponse(BaseModel):
    result: RuntimeRelayControlExecutionResult
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse


class RedisDispatchAckRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    claim_token: str = Field(min_length=1, max_length=512)


class RedisDispatchAckResponse(BaseModel):
    result: RedisDispatchAckResult


class RedisDispatchReleaseRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    claim_token: str = Field(min_length=1, max_length=512)
    reason: str | None = Field(default=None, max_length=255)


class RedisDispatchReleaseResponse(BaseModel):
    result: RedisDispatchReleaseResult


class RedisDispatchPendingInspectionRequest(BaseModel):
    count: int = Field(default=25, ge=1, le=100)
    stale_threshold_ms: int = Field(default=300000, ge=0, le=86400000)
    message_id: str | None = Field(default=None, min_length=1, max_length=128)


class RedisDispatchPendingInspectionResponse(BaseModel):
    result: RedisDispatchPendingInspectionResult


class RedisDispatchRecoveryRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    stale_threshold_ms: int = Field(default=300000, ge=0, le=86400000)


class RedisDispatchRecoveryResponse(BaseModel):
    result: RedisDispatchRecoveryResult


class RedisTransportStatusRequest(BaseModel):
    stale_threshold_ms: int = Field(default=300000, ge=0, le=86400000)
    pending_sample_count: int = Field(default=100, ge=1, le=1000)


class RedisTransportStatusResponse(BaseModel):
    result: RedisTransportStatusResult


class RedisTransportConfigResponse(BaseModel):
    result: RedisTransportConfigResult


class RedisTransportReadinessResponse(BaseModel):
    result: RedisTransportReadinessResult


class DatabaseReadinessDetailResponse(BaseModel):
    result: DatabaseReadinessDetailResult


class PlatformStartupReadinessResponse(BaseModel):
    result: PlatformStartupReadinessResult


class PlatformCurrentReadinessResponse(BaseModel):
    result: PlatformCurrentReadinessResult


class PlatformReadinessComparisonResponse(BaseModel):
    result: PlatformReadinessComparisonResult


class PlatformReadinessHistoryResponse(BaseModel):
    result: PlatformReadinessHistoryResult


class RedisConsumerGroupBootstrapRequest(BaseModel):
    pass


class RedisConsumerGroupBootstrapResponse(BaseModel):
    result: RedisTransportAdminResult


class RedisConsumerGroupResetRequest(BaseModel):
    confirm_destructive_action: bool = False


class RedisConsumerGroupResetResponse(BaseModel):
    result: RedisTransportAdminResult


class ExecuteRuntimePlanResponse(BaseModel):
    plan: ProtocolExecutionPlan
    attempt: CommandExecutionAttemptResponse
    session: ConnectivitySessionHistoryResponse
    outcome: RuntimeCommandOutcome
    result_summary: dict[str, object] | None = None
    response_snapshot: dict[str, object] | None = None
    ingested_batch: MeterReadingBatchResponse | None = None
    ingested_events: list[MeterEventIngestionResponse] = Field(default_factory=list)
    persisted_interval_count: int = 0
    skipped_duplicate_interval_count: int = 0
    post_processing: RuntimePostProcessingResult
    downstream_consumption: DownstreamSignalConsumptionResult
