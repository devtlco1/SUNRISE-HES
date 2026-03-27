from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.readings.enums import (
    ReadingBatchStatus,
    ReadingQuality,
    ReadingSourceType,
    ReadingType,
    SnapshotType,
)


class MeterReadingBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meter_reading_batches"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id"), nullable=False)
    related_command_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("commands.id"))
    related_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("command_execution_attempts.id")
    )
    session_history_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connectivity_session_history.id")
    )
    source_type: Mapped[ReadingSourceType] = mapped_column(
        enum_type(ReadingSourceType, name="reading_source_type"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    status: Mapped[ReadingBatchStatus] = mapped_column(
        enum_type(ReadingBatchStatus, name="reading_batch_status"),
        nullable=False,
        server_default=ReadingBatchStatus.RECEIVED.value,
    )
    reading_context: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    correlation_id: Mapped[str | None] = mapped_column(String(128))

    readings: Mapped[list["MeterReading"]] = relationship(back_populates="batch")
    register_snapshots: Mapped[list["MeterRegisterSnapshot"]] = relationship(back_populates="batch")

    __table_args__ = (
        Index("ix_meter_reading_batches_meter_captured_at", "meter_id", "captured_at"),
        Index("ix_meter_reading_batches_attempt_id", "related_attempt_id"),
        Index("ix_meter_reading_batches_session_history_id", "session_history_id"),
        Index("ix_meter_reading_batches_correlation_id", "correlation_id"),
    )


class MeterReading(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "meter_readings"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meter_reading_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id"), nullable=False)
    obis_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reading_type: Mapped[ReadingType] = mapped_column(
        enum_type(ReadingType, name="reading_type"),
        nullable=False,
    )
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    value_text: Mapped[str | None] = mapped_column(Text())
    value_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unit: Mapped[str | None] = mapped_column(String(32))
    quality: Mapped[ReadingQuality | None] = mapped_column(
        enum_type(ReadingQuality, name="reading_quality")
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)

    batch: Mapped["MeterReadingBatch"] = relationship(back_populates="readings")

    __table_args__ = (
        Index("ix_meter_readings_meter_captured_at", "meter_id", "captured_at"),
        Index("ix_meter_readings_batch_id", "batch_id"),
        Index("ix_meter_readings_obis_code", "obis_code"),
    )


class MeterRegisterSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "meter_register_snapshots"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id"), nullable=False)
    related_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meter_reading_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_type: Mapped[SnapshotType] = mapped_column(
        enum_type(SnapshotType, name="snapshot_type"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128))

    batch: Mapped["MeterReadingBatch"] = relationship(back_populates="register_snapshots")

    __table_args__ = (
        Index("ix_meter_register_snapshots_meter_captured_at", "meter_id", "captured_at"),
        Index("ix_meter_register_snapshots_batch_id", "related_batch_id"),
        Index("ix_meter_register_snapshots_snapshot_type", "snapshot_type"),
    )


class LoadProfileChannel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "load_profile_channels"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id"), nullable=False)
    channel_code: Mapped[str] = mapped_column(String(64), nullable=False)
    obis_code: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    intervals: Mapped[list["LoadProfileInterval"]] = relationship(back_populates="channel")

    __table_args__ = (
        UniqueConstraint("meter_id", "channel_code"),
        Index("ix_load_profile_channels_meter_active", "meter_id", "is_active"),
    )


class LoadProfileInterval(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "load_profile_intervals"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id"), nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("load_profile_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    quality: Mapped[ReadingQuality | None] = mapped_column(
        enum_type(ReadingQuality, name="reading_quality")
    )
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meter_reading_batches.id")
    )

    channel: Mapped["LoadProfileChannel"] = relationship(back_populates="intervals")

    __table_args__ = (
        UniqueConstraint("channel_id", "interval_start", "interval_end"),
        Index("ix_load_profile_intervals_meter_interval_start", "meter_id", "interval_start"),
        Index("ix_load_profile_intervals_source_batch_id", "source_batch_id"),
    )
