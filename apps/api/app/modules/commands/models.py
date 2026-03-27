from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.commands.enums import (
    CommandCategory,
    CommandExecutionAttemptStatus,
    CommandPriority,
    CommandStatus,
    CommandTargetScope,
)


class CommandTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "command_templates"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[CommandCategory] = mapped_column(
        enum_type(CommandCategory, name="command_category"),
        nullable=False,
    )
    target_scope: Mapped[CommandTargetScope] = mapped_column(
        enum_type(CommandTargetScope, name="command_target_scope"),
        nullable=False,
        server_default=CommandTargetScope.METER.value,
    )
    description: Mapped[str | None] = mapped_column(Text())
    payload_schema: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="120")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    commands: Mapped[list["MeterCommand"]] = relationship(back_populates="command_template")

    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_command_templates_category", "category"),
        Index("ix_command_templates_is_active", "is_active"),
    )


class MeterCommand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commands"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id"), nullable=False)
    command_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("command_templates.id"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    endpoint_assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meter_endpoint_assignments.id")
    )
    protocol_association_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("protocol_association_profiles.id")
    )
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    current_status: Mapped[CommandStatus] = mapped_column(
        "status",
        enum_type(CommandStatus, name="command_status"),
        nullable=False,
        server_default=CommandStatus.PENDING.value,
    )
    priority: Mapped[CommandPriority] = mapped_column(
        enum_type(CommandPriority, name="command_priority"),
        nullable=False,
        server_default=CommandPriority.NORMAL.value,
    )
    request_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    normalized_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    result_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    scheduled_at: Mapped[datetime | None] = mapped_column("scheduled_for", DateTime(timezone=True))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_error_code: Mapped[str | None] = mapped_column(String(128))
    latest_error_message: Mapped[str | None] = mapped_column(Text())
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text())

    command_template: Mapped["CommandTemplate"] = relationship(back_populates="commands")
    attempts: Mapped[list["CommandExecutionAttempt"]] = relationship(back_populates="meter_command")

    __table_args__ = (
        UniqueConstraint("correlation_id"),
        UniqueConstraint("idempotency_key"),
        Index("ix_commands_meter_requested_at", "meter_id", "requested_at"),
        Index("ix_commands_status_requested_at", "status", "requested_at"),
        Index("ix_commands_pending_queue_lookup", "status", "queued_at"),
        Index("ix_commands_correlation_id", "correlation_id"),
    )


class CommandExecutionAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "command_execution_attempts"

    meter_command_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("commands.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_runs.id"))
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CommandExecutionAttemptStatus] = mapped_column(
        enum_type(CommandExecutionAttemptStatus, name="command_execution_attempt_status"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_identifier: Mapped[str | None] = mapped_column(String(128))
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communication_endpoints.id"))
    session_history_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connectivity_session_history.id")
    )
    bytes_sent: Mapped[int | None] = mapped_column(Integer)
    bytes_received: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text())
    request_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    response_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    execution_metadata: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    meter_command: Mapped["MeterCommand"] = relationship(back_populates="attempts")

    __table_args__ = (
        UniqueConstraint("meter_command_id", "attempt_number"),
        Index("ix_command_execution_attempts_job_run_id", "job_run_id"),
        Index("ix_command_execution_attempts_active_command", "meter_command_id", "ended_at"),
        Index("ix_command_execution_attempts_worker_status", "worker_identifier", "status", "ended_at"),
        Index("ix_command_execution_attempts_command_started_at", "meter_command_id", "started_at"),
        Index("ix_command_execution_attempts_status_started_at", "status", "started_at"),
    )
