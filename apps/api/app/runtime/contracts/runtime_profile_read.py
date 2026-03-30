from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.modules.commands.enums import CommandCategory
from app.modules.connectivity.enums import ProtocolFamily
from app.runtime.contracts.execution import (
    MeterRuntimeTarget,
    RuntimeExecutionContext,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from app.runtime.contracts.results import RuntimeCommandOutcome, RuntimeReadingBatchPayload
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProfileReadOperation(StringEnum):
    CAPTURE_LOAD_PROFILE = "capture_load_profile"


class RuntimeProfileReadExecutionStatus(StringEnum):
    COMPLETED = "completed"


class RuntimeProfileReadAdapterAcknowledgmentState(StringEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RuntimeProfileReadProtocolStageOutcome(StringEnum):
    PROFILE_READ_COMPLETED = "profile_read_completed"
    PROFILE_READ_FAILED = "profile_read_failed"


class RuntimeProfileReadErrorCategory(StringEnum):
    ADAPTER_REJECTED = "adapter_rejected"
    EXECUTION_FAILED = "execution_failed"


class RuntimeCaptureLoadProfileExecutionCategory(StringEnum):
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class RuntimeCaptureLoadProfileTerminalStatusCategory(StringEnum):
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    UNUSABLE_RESPONSE = "unusable_response"
    BLOCKED_PRE_INVOCATION = "blocked_pre_invocation"
    BLOCKED_MID_PIPELINE = "blocked_mid_pipeline"


class RuntimeProfileReadAdapterRequest(BaseModel):
    adapter_key: str
    protocol_family: ProtocolFamily
    operation: RuntimeProfileReadOperation
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


class RuntimeCaptureLoadProfileExecutionDigest(BaseModel):
    profile_read_execution_record_id: str
    profile_read_operation: RuntimeProfileReadOperation
    command_attempt_id: str
    adapter_key: str
    protocol_family: ProtocolFamily
    resolved_operation_obis_code: str
    validated_target_state: str
    normalized_request_present: bool
    invocation_request_present: bool
    invocation_result_category: str
    interpreter_outcome: RuntimeCommandOutcome
    final_execution_category: RuntimeCaptureLoadProfileExecutionCategory
    load_profile_interval_count: int
    channel_count: int
    correlation_id: str | None = None
    request_id: str | None = None
    session_identifier: str
    summary: str


class RuntimeCaptureLoadProfileTerminalStatus(BaseModel):
    profile_read_execution_record_id: str
    profile_read_operation: RuntimeProfileReadOperation
    command_attempt_id: str
    adapter_key: str
    protocol_family: ProtocolFamily
    terminal_status: RuntimeCaptureLoadProfileTerminalStatusCategory
    invocation_result_category: str | None = None
    digest_execution_category: RuntimeCaptureLoadProfileExecutionCategory | None = None
    interpreter_outcome: RuntimeCommandOutcome | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    session_identifier: str
    summary: str


class RuntimeProfileReadExecutionResult(BaseModel):
    status: RuntimeProfileReadExecutionStatus
    profile_read_execution_record_id: str
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
    profile_read_operation: RuntimeProfileReadOperation
    command_category: CommandCategory
    adapter_acknowledgment_state: RuntimeProfileReadAdapterAcknowledgmentState
    protocol_stage_outcome: RuntimeProfileReadProtocolStageOutcome
    execution_outcome: RuntimeCommandOutcome
    correlation_id: str | None = None
    request_id: str | None = None
    execution_started_at: str
    execution_finished_at: str
    profile_read_batch: RuntimeReadingBatchPayload | None = None
    capture_load_profile_execution_digest: RuntimeCaptureLoadProfileExecutionDigest | None = None
    capture_load_profile_terminal_status: RuntimeCaptureLoadProfileTerminalStatus | None = None
    adapter_result_summary: dict[str, object] = Field(default_factory=dict)
    adapter_response_snapshot: dict[str, object] = Field(default_factory=dict)
    error_category: RuntimeProfileReadErrorCategory | None = None
    error_detail: str | None = None
    profile_read_recorded_by_executor_identifier: str
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
