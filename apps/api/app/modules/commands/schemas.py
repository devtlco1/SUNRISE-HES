from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.commands.enums import (
    CommandApprovalStatus,
    CommandCategory,
    CommandExecutionAttemptStatus,
    CommandOperationalFamily,
    CommandPriority,
    CommandStatus,
    CommandTargetScope,
    OnDemandReadCommandOperation,
    RelayControlCommandOperation,
)
from app.modules.jobs.enums import JobRunStatus
from app.modules.readings.enums import SnapshotType


class CommandTemplateCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    category: CommandCategory
    description: str | None = None
    target_scope: CommandTargetScope = CommandTargetScope.METER
    payload_schema: dict[str, object] | None = None
    timeout_seconds: int = Field(default=120, ge=1, le=86400)
    max_retries: int = Field(default=0, ge=0, le=10)
    is_active: bool = True


class CommandTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    payload_schema: dict[str, object] | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    is_active: bool | None = None


class CommandTemplateResponse(BaseModel):
    id: UUID
    code: str
    name: str
    category: CommandCategory
    description: str | None
    target_scope: CommandTargetScope
    payload_schema: dict[str, object] | None
    timeout_seconds: int
    max_retries: int
    is_active: bool


class CommandTemplateListResponse(BaseModel):
    total: int
    items: list[CommandTemplateResponse]


class MeterCommandCreate(BaseModel):
    command_template_id: UUID
    priority: CommandPriority = CommandPriority.NORMAL
    scheduled_at: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)
    request_payload: dict[str, object] | None = None
    normalized_payload: dict[str, object] | None = None
    endpoint_assignment_id: UUID | None = None
    protocol_association_profile_id: UUID | None = None
    notes: str | None = None


class CaptureLoadProfileCommandCreate(BaseModel):
    command_template_id: UUID
    endpoint_assignment_id: UUID
    protocol_association_profile_id: UUID
    channel_ids: list[UUID] = Field(min_length=1)
    interval_start: datetime
    interval_end: datetime
    priority: CommandPriority = CommandPriority.NORMAL
    scheduled_at: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class RelayControlCommandCreate(BaseModel):
    command_template_id: UUID | None = None
    relay_operation: RelayControlCommandOperation
    endpoint_assignment_id: UUID
    protocol_association_profile_id: UUID
    relay_target_interface_class: str = Field(default="disconnect_control", min_length=1, max_length=64)
    relay_target_obis_code: str = Field(default="0.0.96.3.10.255", min_length=1, max_length=64)
    priority: CommandPriority = CommandPriority.NORMAL
    scheduled_at: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class OnDemandReadCommandCreate(BaseModel):
    command_template_id: UUID | None = None
    on_demand_read_operation: OnDemandReadCommandOperation
    endpoint_assignment_id: UUID
    protocol_association_profile_id: UUID
    priority: CommandPriority = CommandPriority.NORMAL
    scheduled_at: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class BulkCommandWizardRequest(BaseModel):
    family: CommandOperationalFamily
    meter_ids: list[UUID] = Field(min_length=1)
    command_template_id: UUID
    relay_operation: RelayControlCommandOperation | None = None
    on_demand_read_operation: OnDemandReadCommandOperation | None = None
    notes: str | None = None


class BulkCommandWizardResultItem(BaseModel):
    meter_id: UUID
    command_id: UUID | None = None
    command_template_code: str | None = None
    command_family: CommandOperationalFamily
    command_status: CommandStatus | None = None
    approval_status: CommandApprovalStatus | None = None
    submission_status: str
    detail: str | None = None


class BulkCommandWizardResponse(BaseModel):
    submitted_total: int
    failed_total: int
    items: list[BulkCommandWizardResultItem]


class CommandApprovalActionRequest(BaseModel):
    approval_notes: str | None = None


class OnDemandReadAttemptBootstrapRequest(BaseModel):
    bootstrap_identifier: str = Field(min_length=1, max_length=128)
    bootstrap_reason: str | None = Field(default=None, max_length=255)


class OnDemandReadAttemptBootstrapResult(BaseModel):
    bootstrap_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    reused_existing_attempt: bool
    bootstrapped_at: datetime
    bootstrap_identifier: str
    correlation_id: str | None = None
    endpoint_assignment_id: UUID
    endpoint_id: UUID
    protocol_association_profile_id: UUID
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    bootstrap_record: dict[str, object]


class OnDemandReadAttemptBootstrapResponse(BaseModel):
    result: "OnDemandReadAttemptBootstrapResult"
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class OnDemandReadQueuedExecutionEnqueueRequest(BaseModel):
    enqueue_identifier: str = Field(min_length=1, max_length=128)
    enqueue_reason: str | None = Field(default=None, max_length=255)


class OnDemandReadQueuedExecutionMessageSource(BaseModel):
    command_id: UUID
    meter_id: UUID
    endpoint_assignment_id: UUID
    protocol_association_profile_id: UUID
    correlation_id: str | None = None


class OnDemandReadQueuedExecutionMessage(BaseModel):
    contract_family: str
    contract_version: str
    enqueue_identifier: str
    command_category: CommandCategory
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    intended_worker_path: str
    source: OnDemandReadQueuedExecutionMessageSource


class OnDemandReadQueuedExecutionLease(BaseModel):
    stream_name: str
    consumer_group: str
    consumer_name: str
    message_id: str
    claim_token: str
    claim_timeout_seconds: int
    delivery_count: int


class OnDemandReadQueuedExecutionEnqueueResult(BaseModel):
    queue_status: str
    command_id: UUID
    enqueue_identifier: str
    dispatch_request_identity: str
    stream_name: str
    message_id: str
    intended_worker_path: str
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    reused_existing_enqueue: bool
    enqueued_at: datetime
    queue_artifact: dict[str, object]
    queue_message: OnDemandReadQueuedExecutionMessage


class OnDemandReadQueuedExecutionEnqueueResponse(BaseModel):
    result: "OnDemandReadQueuedExecutionEnqueueResult"
    related_command: "MeterCommandResponse"


class OnDemandReadRuntimeHandoffRequest(BaseModel):
    handoff_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    handoff_reason: str | None = Field(default=None, max_length=255)
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)


class OnDemandReadRuntimeHandoffResult(BaseModel):
    handoff_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID
    handoff_identifier: str
    executor_identifier: str
    bootstrap_identifier: str
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    handed_off_at: datetime
    session_identifier: str
    runtime_on_demand_read_execution_present: bool
    runtime_on_demand_read_execution_record_id: str | None = None
    reused_existing_handoff: bool
    reused_existing_runtime_execution: bool
    handoff_record: dict[str, object]


class OnDemandReadRuntimeHandoffResponse(BaseModel):
    result: "OnDemandReadRuntimeHandoffResult"
    job_run: dict[str, object]
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class OnDemandReadRuntimeTerminalizationRequest(BaseModel):
    terminalization_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    terminalization_reason: str | None = Field(default=None, max_length=255)


class OnDemandReadRuntimeTerminalizationResult(BaseModel):
    terminalization_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID | None = None
    terminalization_identifier: str
    executor_identifier: str
    runtime_on_demand_read_execution_record_id: str
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    on_demand_read_execution_outcome: str
    attempt_final_status: CommandExecutionAttemptStatus
    command_final_status: CommandStatus
    job_run_final_status: JobRunStatus | None = None
    terminalization_reason_category: str
    terminalized_at: datetime
    reused_existing_terminalization: bool
    terminalization_record: dict[str, object]


class OnDemandReadRuntimeTerminalizationResponse(BaseModel):
    result: "OnDemandReadRuntimeTerminalizationResult"
    job_run: dict[str, object] | None = None
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class OnDemandReadExecutionOrchestrationRequest(BaseModel):
    orchestration_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    orchestration_reason: str | None = Field(default=None, max_length=255)
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)


class OnDemandReadExecutionOrchestrationResult(BaseModel):
    orchestration_status: str
    orchestration_identifier: str
    executor_identifier: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID | None = None
    runtime_on_demand_read_execution_record_id: str
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    terminalization_artifact_present: bool
    reused_existing_orchestration: bool
    orchestrated_at: datetime
    orchestration_reason_category: str | None = None
    orchestration_record: dict[str, object]


class OnDemandReadExecutionOrchestrationResponse(BaseModel):
    result: "OnDemandReadExecutionOrchestrationResult"
    job_run: dict[str, object] | None = None
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class OnDemandReadExecuteNowRequest(OnDemandReadCommandCreate):
    execute_now_reason: str | None = Field(default=None, max_length=255)


class OnDemandReadQueuedExecuteNowRequest(OnDemandReadCommandCreate):
    queued_execute_now_reason: str | None = Field(default=None, max_length=255)


class OnDemandReadQueuedExecuteNowResult(BaseModel):
    queued_execute_now_status: str
    queued_execute_now_identifier: str
    command_id: UUID
    command_status: CommandStatus
    command_execution_attempt_id: UUID | None = None
    queue_enqueue_status: str
    queue_message_id: str
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    reused_existing_queued_execute_now: bool
    reused_existing_enqueue: bool
    queued_at: datetime
    queued_execute_now_record: dict[str, object]


class OnDemandReadQueuedExecuteNowResponse(BaseModel):
    result: "OnDemandReadQueuedExecuteNowResult"
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: CommandExecutionAttemptResponse | None = None


class OnDemandReadQueuedStatusResult(BaseModel):
    command_id: UUID
    command_status: CommandStatus
    command_execution_attempt_id: UUID | None = None
    queue_enqueue_status: str | None = None
    queue_message_id: str | None = None
    queue_consumption_status: str | None = None
    runtime_on_demand_read_execution_record_id: str | None = None
    on_demand_read_operation: OnDemandReadCommandOperation | None = None
    snapshot_type: SnapshotType | None = None
    worker_consumed: bool
    queued_execute_now_artifact_present: bool
    queue_enqueue_artifact_present: bool
    queue_consumption_artifact_present: bool
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    final_execution_outcome: str | None = None
    reused_existing_queued_execute_now: bool | None = None
    reused_existing_enqueue: bool | None = None
    queued_status_record: dict[str, object]


class OnDemandReadQueuedStatusResponse(BaseModel):
    result: "OnDemandReadQueuedStatusResult"


class OnDemandReadExecuteNowResult(BaseModel):
    execute_now_status: str
    execute_now_identifier: str
    command_id: UUID
    command_status: CommandStatus
    command_execution_attempt_id: UUID
    runtime_on_demand_read_execution_record_id: str
    on_demand_read_operation: OnDemandReadCommandOperation
    snapshot_type: SnapshotType
    on_demand_read_execution_outcome: str | None = None
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    reused_existing_execute_now: bool
    executed_at: datetime
    execute_now_record: dict[str, object]


class OnDemandReadExecuteNowResponse(BaseModel):
    result: "OnDemandReadExecuteNowResult"
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class OnDemandReadExecutionStatusResult(BaseModel):
    command_id: UUID
    command_status: CommandStatus
    on_demand_read_operation: OnDemandReadCommandOperation | None = None
    snapshot_type: SnapshotType | None = None
    command_execution_attempt_id: UUID | None = None
    runtime_on_demand_read_execution_record_id: str | None = None
    on_demand_read_execution_outcome: str | None = None
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    execute_now_artifact_present: bool
    reused_existing_execute_now: bool | None = None
    reused_existing_orchestration: bool | None = None
    reused_existing_terminalization: bool | None = None
    status_record: dict[str, object]


class OnDemandReadExecutionStatusResponse(BaseModel):
    result: "OnDemandReadExecutionStatusResult"


class ConsumeQueuedOnDemandReadExecutionRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    block_ms: int = Field(default=0, ge=0, le=60000)
    ensure_consumer_group: bool = False
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)
    consume_reason: str | None = Field(default=None, max_length=255)


class ConsumeQueuedOnDemandReadExecutionResult(BaseModel):
    consume_status: str
    worker_identifier: str
    queue_message_present: bool
    acked: bool
    consumed_at: datetime
    command_id: UUID | None = None
    command_execution_attempt_id: UUID | None = None
    job_run_id: UUID | None = None
    enqueue_identifier: str | None = None
    on_demand_read_operation: OnDemandReadCommandOperation | None = None
    snapshot_type: SnapshotType | None = None
    on_demand_read_execution_outcome: str | None = None
    runtime_on_demand_read_execution_record_id: str | None = None
    queue_lease: OnDemandReadQueuedExecutionLease | None = None
    queue_message: OnDemandReadQueuedExecutionMessage | None = None
    queue_consumption_record: dict[str, object] | None = None


class ConsumeQueuedOnDemandReadExecutionResponse(BaseModel):
    result: "ConsumeQueuedOnDemandReadExecutionResult"
    related_command: MeterCommandResponse | None = None
    created_or_existing_attempt: CommandExecutionAttemptResponse | None = None
    job_run: dict[str, object] | None = None


class RelayControlAttemptBootstrapRequest(BaseModel):
    bootstrap_identifier: str = Field(min_length=1, max_length=128)
    bootstrap_reason: str | None = Field(default=None, max_length=255)


class RelayControlAttemptBootstrapResult(BaseModel):
    bootstrap_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    reused_existing_attempt: bool
    bootstrapped_at: datetime
    bootstrap_identifier: str
    correlation_id: str | None = None
    endpoint_assignment_id: UUID
    endpoint_id: UUID
    protocol_association_profile_id: UUID
    relay_control_operation: RelayControlCommandOperation
    bootstrap_record: dict[str, object]


class RelayControlAttemptBootstrapResponse(BaseModel):
    result: RelayControlAttemptBootstrapResult
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class RelayControlRuntimeHandoffRequest(BaseModel):
    handoff_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    handoff_reason: str | None = Field(default=None, max_length=255)
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)


class RelayControlRuntimeHandoffResult(BaseModel):
    handoff_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID
    handoff_identifier: str
    executor_identifier: str
    bootstrap_identifier: str
    relay_control_operation: RelayControlCommandOperation
    handed_off_at: datetime
    session_identifier: str
    runtime_relay_control_execution_present: bool
    runtime_relay_control_execution_record_id: str | None = None
    reused_existing_handoff: bool
    reused_existing_runtime_execution: bool
    handoff_record: dict[str, object]


class RelayControlRuntimeHandoffResponse(BaseModel):
    result: RelayControlRuntimeHandoffResult
    job_run: dict[str, object]
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class RelayControlRuntimeTerminalizationRequest(BaseModel):
    terminalization_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    terminalization_reason: str | None = Field(default=None, max_length=255)


class RelayControlRuntimeTerminalizationResult(BaseModel):
    terminalization_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID | None = None
    terminalization_identifier: str
    executor_identifier: str
    runtime_relay_control_execution_record_id: str
    relay_control_operation: RelayControlCommandOperation
    relay_control_execution_outcome: str
    attempt_final_status: CommandExecutionAttemptStatus
    command_final_status: CommandStatus
    job_run_final_status: JobRunStatus | None = None
    terminalization_reason_category: str
    terminalized_at: datetime
    reused_existing_terminalization: bool
    terminalization_record: dict[str, object]


class RelayControlRuntimeTerminalizationResponse(BaseModel):
    result: RelayControlRuntimeTerminalizationResult
    job_run: dict[str, object] | None = None
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class RelayControlExecutionOrchestrationRequest(BaseModel):
    orchestration_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    orchestration_reason: str | None = Field(default=None, max_length=255)
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)


class RelayControlExecutionOrchestrationResult(BaseModel):
    orchestration_status: str
    orchestration_identifier: str
    executor_identifier: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID | None = None
    runtime_relay_control_execution_record_id: str
    relay_control_operation: RelayControlCommandOperation
    terminalization_artifact_present: bool
    reused_existing_orchestration: bool
    orchestrated_at: datetime
    orchestration_reason_category: str | None = None
    orchestration_record: dict[str, object]


class RelayControlExecutionOrchestrationResponse(BaseModel):
    result: RelayControlExecutionOrchestrationResult
    job_run: dict[str, object] | None = None
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class RelayControlExecuteNowRequest(RelayControlCommandCreate):
    execute_now_reason: str | None = Field(default=None, max_length=255)


class RelayControlExecuteNowResult(BaseModel):
    execute_now_status: str
    execute_now_identifier: str
    command_id: UUID
    command_status: CommandStatus
    command_execution_attempt_id: UUID
    runtime_relay_control_execution_record_id: str
    relay_control_operation: RelayControlCommandOperation
    relay_control_execution_outcome: str | None = None
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    reused_existing_execute_now: bool
    executed_at: datetime
    execute_now_record: dict[str, object]


class RelayControlExecuteNowResponse(BaseModel):
    result: RelayControlExecuteNowResult
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class RelayControlExecutionStatusResult(BaseModel):
    command_id: UUID
    command_status: CommandStatus
    relay_control_operation: RelayControlCommandOperation | None = None
    command_execution_attempt_id: UUID | None = None
    runtime_relay_control_execution_record_id: str | None = None
    relay_control_execution_outcome: str | None = None
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    execute_now_artifact_present: bool
    reused_existing_execute_now: bool | None = None
    reused_existing_orchestration: bool | None = None
    reused_existing_terminalization: bool | None = None
    status_record: dict[str, object]


class RelayControlExecutionStatusResponse(BaseModel):
    result: RelayControlExecutionStatusResult


class ProfileCaptureAttemptBootstrapRequest(BaseModel):
    bootstrap_identifier: str = Field(min_length=1, max_length=128)
    bootstrap_reason: str | None = Field(default=None, max_length=255)


class ProfileCaptureAttemptBootstrapResult(BaseModel):
    bootstrap_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    reused_existing_attempt: bool
    bootstrapped_at: datetime
    bootstrap_identifier: str
    correlation_id: str | None = None
    endpoint_assignment_id: UUID
    endpoint_id: UUID
    protocol_association_profile_id: UUID
    bootstrap_record: dict[str, object]


class ProfileCaptureAttemptBootstrapResponse(BaseModel):
    result: ProfileCaptureAttemptBootstrapResult
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class ProfileCaptureQueuedExecutionEnqueueRequest(BaseModel):
    enqueue_identifier: str = Field(min_length=1, max_length=128)
    enqueue_reason: str | None = Field(default=None, max_length=255)


class ProfileCaptureQueuedExecutionMessageSource(BaseModel):
    command_id: UUID
    meter_id: UUID
    endpoint_assignment_id: UUID
    protocol_association_profile_id: UUID
    correlation_id: str | None = None


class ProfileCaptureQueuedExecutionMessage(BaseModel):
    contract_family: str
    contract_version: str
    enqueue_identifier: str
    command_category: CommandCategory
    profile_read_operation: str
    interval_start: datetime
    interval_end: datetime
    channel_ids: list[UUID]
    channel_count: int
    intended_worker_path: str
    source: ProfileCaptureQueuedExecutionMessageSource


class ProfileCaptureQueuedExecutionLease(BaseModel):
    stream_name: str
    consumer_group: str
    consumer_name: str
    message_id: str
    claim_token: str
    claim_timeout_seconds: int
    delivery_count: int


class ProfileCaptureQueuedExecutionEnqueueResult(BaseModel):
    queue_status: str
    command_id: UUID
    enqueue_identifier: str
    dispatch_request_identity: str
    stream_name: str
    message_id: str
    intended_worker_path: str
    profile_read_operation: str
    reused_existing_enqueue: bool
    enqueued_at: datetime
    queue_artifact: dict[str, object]
    queue_message: ProfileCaptureQueuedExecutionMessage


class ProfileCaptureQueuedExecutionEnqueueResponse(BaseModel):
    result: ProfileCaptureQueuedExecutionEnqueueResult
    related_command: "MeterCommandResponse"


class ProfileCaptureRuntimeHandoffRequest(BaseModel):
    handoff_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    handoff_reason: str | None = Field(default=None, max_length=255)
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)


class ProfileCaptureRuntimeHandoffResult(BaseModel):
    handoff_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID
    handoff_identifier: str
    executor_identifier: str
    bootstrap_identifier: str
    handed_off_at: datetime
    session_identifier: str
    runtime_profile_read_execution_present: bool
    runtime_profile_read_execution_record_id: str | None = None
    reused_existing_handoff: bool
    reused_existing_runtime_execution: bool
    handoff_record: dict[str, object]


class ProfileCaptureRuntimeHandoffResponse(BaseModel):
    result: ProfileCaptureRuntimeHandoffResult
    job_run: dict[str, object]
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class ProfileCaptureRuntimeTerminalizationRequest(BaseModel):
    terminalization_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    terminalization_reason: str | None = Field(default=None, max_length=255)


class ProfileCaptureRuntimeTerminalizationResult(BaseModel):
    terminalization_status: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID | None = None
    terminalization_identifier: str
    executor_identifier: str
    runtime_profile_read_execution_record_id: str
    runtime_capture_load_profile_terminal_status: str
    attempt_final_status: CommandExecutionAttemptStatus
    command_final_status: CommandStatus
    job_run_final_status: JobRunStatus | None = None
    terminalization_reason_category: str
    terminalized_at: datetime
    reused_existing_terminalization: bool
    terminalization_record: dict[str, object]


class ProfileCaptureRuntimeTerminalizationResponse(BaseModel):
    result: ProfileCaptureRuntimeTerminalizationResult
    job_run: dict[str, object] | None = None
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class ProfileCaptureExecutionOrchestrationRequest(BaseModel):
    orchestration_identifier: str = Field(min_length=1, max_length=128)
    executor_identifier: str = Field(min_length=1, max_length=128)
    orchestration_reason: str | None = Field(default=None, max_length=255)
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)


class ProfileCaptureExecutionOrchestrationResult(BaseModel):
    orchestration_status: str
    orchestration_identifier: str
    executor_identifier: str
    command_id: UUID
    command_execution_attempt_id: UUID
    job_run_id: UUID | None = None
    runtime_profile_read_execution_record_id: str
    terminalization_artifact_present: bool
    reused_existing_orchestration: bool
    orchestrated_at: datetime
    orchestration_reason_category: str | None = None
    orchestration_record: dict[str, object]


class ProfileCaptureExecutionOrchestrationResponse(BaseModel):
    result: ProfileCaptureExecutionOrchestrationResult
    job_run: dict[str, object] | None = None
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class ProfileCaptureExecuteNowRequest(CaptureLoadProfileCommandCreate):
    execute_now_reason: str | None = Field(default=None, max_length=255)


class ProfileCaptureExecuteNowResult(BaseModel):
    execute_now_status: str
    execute_now_identifier: str
    command_id: UUID
    command_status: CommandStatus
    command_execution_attempt_id: UUID
    runtime_profile_read_execution_record_id: str
    terminal_status_category: str | None = None
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    reused_existing_execute_now: bool
    executed_at: datetime
    execute_now_record: dict[str, object]


class ProfileCaptureExecuteNowResponse(BaseModel):
    result: ProfileCaptureExecuteNowResult
    related_command: "MeterCommandResponse"
    created_or_existing_attempt: "CommandExecutionAttemptResponse"


class ProfileCaptureExecutionStatusResult(BaseModel):
    command_id: UUID
    command_status: CommandStatus
    command_execution_attempt_id: UUID | None = None
    runtime_profile_read_execution_record_id: str | None = None
    terminal_status_category: str | None = None
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    execute_now_artifact_present: bool
    reused_existing_execute_now: bool | None = None
    reused_existing_orchestration: bool | None = None
    reused_existing_terminalization: bool | None = None
    status_record: dict[str, object]


class ProfileCaptureExecutionStatusResponse(BaseModel):
    result: ProfileCaptureExecutionStatusResult


class ConsumeQueuedProfileCaptureExecutionRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    block_ms: int = Field(default=0, ge=0, le=60000)
    ensure_consumer_group: bool = False
    lease_seconds: int = Field(default=300, ge=5, le=3600)
    session_timeout_seconds: int = Field(default=300, ge=5, le=3600)
    consume_reason: str | None = Field(default=None, max_length=255)


class ConsumeQueuedProfileCaptureExecutionResult(BaseModel):
    consume_status: str
    worker_identifier: str
    queue_message_present: bool
    acked: bool
    consumed_at: datetime
    command_id: UUID | None = None
    command_execution_attempt_id: UUID | None = None
    job_run_id: UUID | None = None
    enqueue_identifier: str | None = None
    profile_read_operation: str | None = None
    terminal_status_category: str | None = None
    runtime_profile_read_execution_record_id: str | None = None
    queue_lease: ProfileCaptureQueuedExecutionLease | None = None
    queue_message: ProfileCaptureQueuedExecutionMessage | None = None
    queue_consumption_record: dict[str, object] | None = None


class ConsumeQueuedProfileCaptureExecutionResponse(BaseModel):
    result: ConsumeQueuedProfileCaptureExecutionResult
    related_command: MeterCommandResponse | None = None
    created_or_existing_attempt: CommandExecutionAttemptResponse | None = None
    job_run: dict[str, object] | None = None


class CommandExecutionAttemptResponse(BaseModel):
    id: UUID
    meter_command_id: UUID
    job_run_id: UUID | None
    attempt_number: int
    status: CommandExecutionAttemptStatus
    started_at: datetime
    ended_at: datetime | None
    worker_identifier: str | None
    endpoint_id: UUID | None
    session_history_id: UUID | None
    bytes_sent: int | None
    bytes_received: int | None
    latency_ms: int | None
    error_code: str | None
    error_message: str | None
    request_snapshot: dict[str, object] | None
    response_snapshot: dict[str, object] | None
    execution_metadata: dict[str, object] | None


class CommandExecutionAttemptListResponse(BaseModel):
    total: int
    items: list[CommandExecutionAttemptResponse]


class MeterCommandResponse(BaseModel):
    id: UUID
    meter_id: UUID
    command_template_id: UUID
    command_template_code: str
    command_template_name: str
    current_status: CommandStatus
    approval_status: CommandApprovalStatus
    approval_reviewed_at: datetime | None
    approval_reviewed_by_user_id: UUID | None
    approval_notes: str | None
    priority: CommandPriority
    requested_by_user_id: UUID | None
    requested_at: datetime
    scheduled_at: datetime | None
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    timeout_at: datetime | None
    correlation_id: str | None
    idempotency_key: str | None
    request_payload: dict[str, object] | None
    normalized_payload: dict[str, object] | None
    result_summary: dict[str, object] | None
    latest_error_code: str | None
    latest_error_message: str | None
    max_retries: int
    retry_count: int
    endpoint_assignment_id: UUID | None
    protocol_association_profile_id: UUID | None
    notes: str | None


class MeterCommandDetailResponse(MeterCommandResponse):
    attempts: list[CommandExecutionAttemptResponse]


class CommandOperationalDetailResult(BaseModel):
    command_id: UUID
    command_family: CommandOperationalFamily
    command_category: CommandCategory
    command_status: CommandStatus
    approval_status: CommandApprovalStatus
    approval_reviewed_at: datetime | None = None
    approval_reviewed_by_user_id: UUID | None = None
    approval_notes: str | None = None
    meter_id: UUID
    command_template_code: str
    latest_command_execution_attempt_id: UUID | None = None
    latest_command_execution_attempt_status: CommandExecutionAttemptStatus | None = None
    runtime_execution_record_id: str | None = None
    family_specific_outcome_summary: dict[str, object] = Field(default_factory=dict)
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    execute_now_artifact_present: bool
    created_at: datetime
    latest_updated_at: datetime
    projection_record: dict[str, object] = Field(default_factory=dict)


class CommandOperationalDetailResponse(BaseModel):
    result: CommandOperationalDetailResult


class CommandOperationalRecentListItem(BaseModel):
    command_id: UUID
    command_family: CommandOperationalFamily
    command_category: CommandCategory
    command_status: CommandStatus
    approval_status: CommandApprovalStatus
    approval_reviewed_at: datetime | None = None
    approval_notes: str | None = None
    meter_id: UUID
    command_template_code: str
    latest_command_execution_attempt_id: UUID | None = None
    latest_command_execution_attempt_status: CommandExecutionAttemptStatus | None = None
    runtime_execution_record_id: str | None = None
    family_specific_outcome_summary: dict[str, object] = Field(default_factory=dict)
    orchestration_artifact_present: bool
    terminalization_artifact_present: bool
    execute_now_artifact_present: bool
    created_at: datetime
    latest_updated_at: datetime


class CommandOperationalRecentListResponse(BaseModel):
    total: int
    limit: int
    family_filter: CommandOperationalFamily | None = None
    approval_filter: CommandApprovalStatus | None = None
    items: list[CommandOperationalRecentListItem]


class MeterScopedCommandOperationalRecentListItem(CommandOperationalRecentListItem):
    pass


class MeterScopedCommandOperationalRecentListResponse(BaseModel):
    meter_id: UUID
    total: int
    limit: int
    family_filter: CommandOperationalFamily | None = None
    items: list[MeterScopedCommandOperationalRecentListItem]


class MeterCommandListResponse(BaseModel):
    total: int
    items: list[MeterCommandResponse]
