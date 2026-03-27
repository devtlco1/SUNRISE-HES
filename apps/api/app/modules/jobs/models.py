from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.commands.enums import CommandPriority, CommandStatus
from app.modules.jobs.enums import JobCategory, JobRunStatus, JobScheduleType, JobTargetType


class JobDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    code: Mapped[str] = mapped_column("job_key", String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[JobCategory] = mapped_column(
        "job_type",
        enum_type(JobCategory, name="job_category"),
        nullable=False,
    )
    target_type: Mapped[JobTargetType] = mapped_column(
        enum_type(JobTargetType, name="job_target_type"),
        nullable=False,
        server_default=JobTargetType.SYSTEM.value,
    )
    schedule_type: Mapped[JobScheduleType] = mapped_column(
        enum_type(JobScheduleType, name="job_schedule_type"),
        nullable=False,
        server_default=JobScheduleType.MANUAL.value,
    )
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cron_expression: Mapped[str | None] = mapped_column("schedule_expression", String(128))
    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    command_template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("command_templates.id"))
    default_payload: Mapped[dict[str, object] | None] = mapped_column("config_json", JSONB)
    priority: Mapped[CommandPriority] = mapped_column(
        enum_type(CommandPriority, name="command_priority"),
        nullable=False,
        server_default=CommandPriority.NORMAL.value,
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="120")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column("enabled", nullable=False, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text())
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    runs: Mapped[list["JobRun"]] = relationship(back_populates="job_definition")
    targets: Mapped[list["JobDefinitionTargetAssignment"]] = relationship(back_populates="job_definition")

    __table_args__ = (
        UniqueConstraint("job_key"),
        Index("ix_jobs_job_type", "job_type"),
        Index("ix_jobs_schedule_type", "schedule_type"),
        Index("ix_jobs_enabled", "enabled"),
    )


class JobRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_runs"

    job_definition_id: Mapped[uuid.UUID] = mapped_column(
        "job_id",
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_meter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meters.id"))
    target_endpoint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("communication_endpoints.id"))
    related_command_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("commands.id"))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_identifier: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[JobRunStatus] = mapped_column(
        enum_type(JobRunStatus, name="job_run_status"),
        nullable=False,
        server_default=JobRunStatus.PENDING.value,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column("finished_at", DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    request_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    result_summary: Mapped[dict[str, object] | None] = mapped_column("summary_json", JSONB)
    latest_error_code: Mapped[str | None] = mapped_column(String(128))
    latest_error_message: Mapped[str | None] = mapped_column("error_message", Text())

    job_definition: Mapped["JobDefinition"] = relationship(back_populates="runs")
    related_command: Mapped["MeterCommand | None"] = relationship(
        "MeterCommand",
        foreign_keys=[related_command_id],
    )

    __table_args__ = (
        UniqueConstraint("correlation_id"),
        Index("ix_job_runs_job_status", "job_id", "status"),
        Index("ix_job_runs_claimable_lookup", "status", "available_at", "claim_expires_at"),
        Index("ix_job_runs_worker_identifier", "worker_identifier"),
        Index("ix_job_runs_recent_history", "scheduled_for", "status"),
        Index(
            "uq_job_runs_job_meter_scheduled_for",
            "job_id",
            "target_meter_id",
            "scheduled_for",
            unique=True,
            postgresql_where=text("target_meter_id IS NOT NULL"),
        ),
        Index(
            "uq_job_runs_job_system_scheduled_for",
            "job_id",
            "scheduled_for",
            unique=True,
            postgresql_where=text("target_meter_id IS NULL AND target_endpoint_id IS NULL"),
        ),
    )


class JobDefinitionTargetAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_definition_target_assignments"

    job_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_meter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meters.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text())

    job_definition: Mapped["JobDefinition"] = relationship(back_populates="targets")

    __table_args__ = (
        UniqueConstraint("job_definition_id", "target_meter_id"),
        Index("ix_job_definition_target_assignments_job_active", "job_definition_id", "is_active"),
        Index("ix_job_definition_target_assignments_meter_active", "target_meter_id", "is_active"),
    )
