from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.modules.commands.enums import CommandCategory
from app.modules.connectivity.enums import ProtocolFamily
from app.modules.readings.enums import SnapshotType
from app.runtime.contracts.execution import (
    MeterRuntimeTarget,
    RuntimeExecutionContext,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from app.runtime.contracts.results import RuntimeCommandOutcome, RuntimeRegisterSnapshotPayload
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeOnDemandReadOperation(StringEnum):
    READ_BILLING_SNAPSHOT = "read_billing_snapshot"


class RuntimeOnDemandReadExecutionStatus(StringEnum):
    COMPLETED = "completed"


class RuntimeOnDemandReadAdapterAcknowledgmentState(StringEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RuntimeOnDemandReadProtocolStageOutcome(StringEnum):
    BILLING_SNAPSHOT_COMPLETED = "billing_snapshot_completed"
    BILLING_SNAPSHOT_FAILED = "billing_snapshot_failed"


class RuntimeOnDemandReadErrorCategory(StringEnum):
    ADAPTER_REJECTED = "adapter_rejected"
    EXECUTION_FAILED = "execution_failed"


class RuntimeOnDemandReadAdapterRequest(BaseModel):
    adapter_key: str
    protocol_family: ProtocolFamily
    operation: RuntimeOnDemandReadOperation
    command_category: CommandCategory
    execution_context: RuntimeExecutionContext
    target: MeterRuntimeTarget
    transport: RuntimeTransportConfig
    security: RuntimeSecurityMaterialRefs
    request_payload: dict[str, object] | None = None
    normalized_payload: dict[str, object] | None = None
    dispatch_envelope_record_id: str
    trace_references: dict[str, object] = Field(default_factory=dict)
    lineage: RuntimeExecutionSessionLineage


class RuntimeOnDemandReadExecutionResult(BaseModel):
    status: RuntimeOnDemandReadExecutionStatus
    on_demand_read_execution_record_id: str
    session_identifier: str
    dispatch_envelope_record_id: str
    delivery_contract_record_id: str
    envelope_record_id: str
    publication_contract_record_id: str
    attestation_record_id: str
    settlement_record_id: str
    reconciliation_record_id: str
    interpretation_record_id: str
    observation_record_id: str
    invocation_result_record_id: str
    dispatch_request_record_id: str
    selection_record_id: str
    intent_record_id: str
    closure_record_id: str
    materialization_record_id: str
    post_processing_record_id: str
    disposition_record_id: str
    outcome_record_id: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    adapter_key: str
    protocol_family: ProtocolFamily
    on_demand_read_operation: RuntimeOnDemandReadOperation
    snapshot_type: SnapshotType
    command_category: CommandCategory
    adapter_acknowledgment_state: RuntimeOnDemandReadAdapterAcknowledgmentState
    protocol_stage_outcome: RuntimeOnDemandReadProtocolStageOutcome
    execution_outcome: RuntimeCommandOutcome
    correlation_id: str | None = None
    request_id: str | None = None
    execution_started_at: str
    execution_finished_at: str
    register_snapshot: RuntimeRegisterSnapshotPayload | None = None
    adapter_result_summary: dict[str, object] = Field(default_factory=dict)
    adapter_response_snapshot: dict[str, object] = Field(default_factory=dict)
    error_category: RuntimeOnDemandReadErrorCategory | None = None
    error_detail: str | None = None
    on_demand_read_recorded_by_executor_identifier: str
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
