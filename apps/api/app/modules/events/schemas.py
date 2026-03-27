from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.events.enums import EventSeverity, EventState


class MeterEventIngestionResponse(BaseModel):
    id: UUID
    meter_id: UUID | None
    related_batch_id: UUID | None
    related_attempt_id: UUID | None
    event_code: str
    event_name: str | None
    severity: EventSeverity
    event_state: EventState
    occurred_at: datetime
    received_at: datetime
    raw_payload: dict[str, object] | None
    normalized_payload: dict[str, object] | None
    correlation_id: str | None


class MeterEventIngestionListResponse(BaseModel):
    total: int
    items: list[MeterEventIngestionResponse]


class MeterEventIngestItem(BaseModel):
    event_code: str = Field(min_length=1, max_length=128)
    event_name: str | None = Field(default=None, max_length=255)
    severity: EventSeverity
    event_state: EventState
    occurred_at: datetime
    raw_payload: dict[str, object] | None = None
    normalized_payload: dict[str, object] | None = None


class IngestMeterEventsRequest(BaseModel):
    related_batch_id: UUID | None = None
    related_attempt_id: UUID | None = None
    received_at: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    events: list[MeterEventIngestItem]


class IngestMeterEventsResponse(BaseModel):
    total_ingested: int
    items: list[MeterEventIngestionResponse]
