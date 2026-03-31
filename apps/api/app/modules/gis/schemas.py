from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GisLiteEntityResponse(BaseModel):
    meter_id: UUID
    meter_serial_number: str
    meter_status: str
    meter_last_seen_at: datetime | None = None
    service_point_id: UUID | None = None
    service_point_code: str | None = None
    address_line: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    has_coordinates: bool
    subscriber_id: UUID | None = None
    subscriber_display_name: str | None = None
    subscriber_type: str | None = None
    account_id: UUID | None = None
    account_number: str | None = None
    location_presence: str = Field(pattern="^(coordinates_available|service_point_only|unlinked)$")


class GisLiteEntityListResponse(BaseModel):
    total: int
    items: list[GisLiteEntityResponse]
