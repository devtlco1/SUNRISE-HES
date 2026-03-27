from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import UUIDPrimaryKeyMixin
from app.modules.events.enums import EventSeverity, EventState


class MeterEventIngestion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "meter_events"

    meter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meters.id"))
    related_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meter_reading_batches.id"))
    related_attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("command_execution_attempts.id"))
    event_code: Mapped[str] = mapped_column(String(128), nullable=False)
    event_name: Mapped[str | None] = mapped_column("title", String(255))
    severity: Mapped[EventSeverity] = mapped_column(
        enum_type(EventSeverity, name="event_severity"),
        nullable=False,
        server_default=EventSeverity.INFO.value,
    )
    event_state: Mapped[EventState] = mapped_column(
        "state",
        enum_type(EventState, name="event_state"),
        nullable=False,
        server_default=EventState.OPEN.value,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    raw_payload: Mapped[dict[str, object] | None] = mapped_column("payload", JSONB)
    normalized_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_meter_events_meter_occurred_at", "meter_id", "occurred_at"),
        Index("ix_meter_events_state_severity", "state", "severity"),
        Index("ix_meter_events_event_code", "event_code"),
        Index("ix_meter_events_correlation_id", "correlation_id"),
    )
