from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.commands.enums import (
    CommandCategory,
    CommandExecutionAttemptStatus,
    CommandPriority,
    CommandStatus,
    CommandTargetScope,
)
from app.modules.jobs.enums import JobRunStatus


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


class MeterCommandListResponse(BaseModel):
    total: int
    items: list[MeterCommandResponse]
