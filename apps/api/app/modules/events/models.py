from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.events.enums import EventSeverity, EventState


class MeterEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meter_events"

    meter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meters.id"))
    related_command_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("commands.id"))
    event_code: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[EventSeverity] = mapped_column(
        enum_type(EventSeverity, name="event_severity"),
        nullable=False,
        server_default=EventSeverity.INFO.value,
    )
    state: Mapped[EventState] = mapped_column(
        enum_type(EventState, name="event_state"),
        nullable=False,
        server_default=EventState.OPEN.value,
    )
    source: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    message: Mapped[str | None] = mapped_column(Text())
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_meter_events_meter_occurred_at", "meter_id", "occurred_at"),
        Index("ix_meter_events_state_severity", "state", "severity"),
        Index("ix_meter_events_event_code", "event_code"),
    )
