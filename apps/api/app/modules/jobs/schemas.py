from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.commands.enums import CommandPriority, CommandStatus
from app.modules.commands.schemas import CommandExecutionAttemptResponse, MeterCommandResponse
from app.modules.jobs.enums import JobCategory, JobRunStatus, JobScheduleType, JobTargetType


class JobDefinitionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    category: JobCategory
    target_type: JobTargetType
    schedule_type: JobScheduleType
    run_at: datetime | None = None
    cron_expression: str | None = Field(default=None, max_length=128)
    interval_seconds: int | None = Field(default=None, ge=1)
    command_template_id: UUID | None = None
    default_payload: dict[str, object] | None = None
    priority: CommandPriority = CommandPriority.NORMAL
    timeout_seconds: int = Field(default=120, ge=1, le=86400)
    max_retries: int = Field(default=0, ge=0, le=50)
    is_active: bool = True
    notes: str | None = None


class JobDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    run_at: datetime | None = None
    cron_expression: str | None = Field(default=None, max_length=128)
    interval_seconds: int | None = Field(default=None, ge=1)
    command_template_id: UUID | None = None
    default_payload: dict[str, object] | None = None
    priority: CommandPriority | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    max_retries: int | None = Field(default=None, ge=0, le=50)
    is_active: bool | None = None
    notes: str | None = None


class JobDefinitionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    category: JobCategory
    target_type: JobTargetType
    schedule_type: JobScheduleType
    run_at: datetime | None
    cron_expression: str | None
    interval_seconds: int | None
    command_template_id: UUID | None
    default_payload: dict[str, object] | None
    priority: CommandPriority
    timeout_seconds: int
    max_retries: int
    is_active: bool
    notes: str | None


class JobDefinitionListResponse(BaseModel):
    total: int
    items: list[JobDefinitionResponse]


class JobDefinitionTargetAssignmentCreate(BaseModel):
    target_meter_id: UUID
    notes: str | None = None


class JobDefinitionTargetAssignmentResponse(BaseModel):
    id: UUID
    job_definition_id: UUID
    target_meter_id: UUID
    assigned_at: datetime
    unassigned_at: datetime | None
    is_active: bool
    notes: str | None


class JobDefinitionTargetAssignmentListResponse(BaseModel):
    total: int
    items: list[JobDefinitionTargetAssignmentResponse]


class ManualJobRunCreate(BaseModel):
    target_meter_id: UUID | None = None
    target_endpoint_id: UUID | None = None
    scheduled_for: datetime | None = None
    available_at: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    request_payload: dict[str, object] | None = None


class JobRunResponse(BaseModel):
    id: UUID
    job_definition_id: UUID
    target_meter_id: UUID | None
    target_endpoint_id: UUID | None
    related_command_id: UUID | None
    scheduled_for: datetime
    available_at: datetime
    claimed_at: datetime | None
    claim_expires_at: datetime | None
    worker_identifier: str | None
    status: JobRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    retry_count: int
    max_retries: int
    request_payload: dict[str, object] | None
    result_summary: dict[str, object] | None
    latest_error_code: str | None
    latest_error_message: str | None
    correlation_id: str | None
    related_command: "JobRunRelatedCommandSummary | None" = None


class JobRunListResponse(BaseModel):
    total: int
    items: list[JobRunResponse]


class WorkerClaimRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=10, ge=1, le=100)
    lease_seconds: int = Field(default=60, ge=5, le=3600)


class WorkerClaimResponse(BaseModel):
    claimed_count: int
    items: list[JobRunResponse]


class WorkerLeaseRenewRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=60, ge=5, le=3600)


class JobRunCompleteRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    result_summary: dict[str, object] | None = None
    related_command_id: UUID | None = None


class JobRunFailRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    latest_error_code: str | None = Field(default=None, max_length=128)
    latest_error_message: str | None = None
    result_summary: dict[str, object] | None = None
    retry_delay_seconds: int | None = Field(default=None, ge=0, le=86400)


class CommandCancelRequest(BaseModel):
    reason: str | None = None


class CommandCancelResponse(BaseModel):
    command_id: UUID
    previous_status: CommandStatus
    current_status: CommandStatus
    latest_error_message: str | None


class JobRunRelatedCommandSummary(BaseModel):
    id: UUID
    current_status: CommandStatus
    command_template_id: UUID
    command_template_code: str


class MaterializeCommandResponse(BaseModel):
    materialized: bool
    job_run: JobRunResponse
    command: "MeterCommandResponse"


class GenerateDueRunsRequest(BaseModel):
    as_of: datetime | None = None
    window_seconds: int = Field(default=300, ge=1, le=86400)
    limit_per_definition: int = Field(default=100, ge=1, le=1000)
    job_definition_id: UUID | None = None


class GenerateDueRunsResponse(BaseModel):
    created_count: int
    skipped_existing_count: int
    items: list[JobRunResponse]


class StartCommandAttemptRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    meter_command_id: UUID
    endpoint_id: UUID | None = None
    session_history_id: UUID | None = None
    request_snapshot: dict[str, object] | None = None
    execution_metadata: dict[str, object] | None = None


class MarkCommandAttemptRunningRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    execution_metadata: dict[str, object] | None = None


class CommandAttemptSucceedRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    response_snapshot: dict[str, object] | None = None
    result_summary: dict[str, object] | None = None
    bytes_sent: int | None = Field(default=None, ge=0)
    bytes_received: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    session_history_id: UUID | None = None


class CommandAttemptFailRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = None
    response_snapshot: dict[str, object] | None = None
    execution_metadata: dict[str, object] | None = None
    bytes_sent: int | None = Field(default=None, ge=0)
    bytes_received: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    session_history_id: UUID | None = None
    retry_delay_seconds: int | None = Field(default=None, ge=0, le=86400)


class CommandAttemptTimeoutRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    error_message: str | None = None
    execution_metadata: dict[str, object] | None = None
    session_history_id: UUID | None = None
    retry_delay_seconds: int | None = Field(default=None, ge=0, le=86400)


class PrepareJobRunForExecutionRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=60, ge=5, le=3600)
    endpoint_id: UUID | None = None
    session_history_id: UUID | None = None
    request_snapshot: dict[str, object] | None = None
    execution_metadata: dict[str, object] | None = None


class PrepareJobRunForExecutionResponse(BaseModel):
    job_run: JobRunResponse
    related_command: MeterCommandResponse
    created_or_existing_attempt: CommandExecutionAttemptResponse
    job_run_claimed: bool
    command_materialized: bool
    attempt_started: bool
