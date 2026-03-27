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
