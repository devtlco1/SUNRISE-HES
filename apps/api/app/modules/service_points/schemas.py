from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ServicePointListItemResponse(BaseModel):
    id: UUID
    service_point_code: str
    address_line: str | None = None
    premises_type: str | None = None
    is_active: bool
    latitude: float | None = None
    longitude: float | None = None
    linked_meter_count: int = Field(ge=0)
    linked_subscriber_count: int = Field(ge=0)
    linked_account_count: int = Field(ge=0)
    primary_meter_serial_number: str | None = None
    primary_subscriber_display_name: str | None = None


class ServicePointListResponse(BaseModel):
    total: int
    items: list[ServicePointListItemResponse]


class ServicePointLinkedMeterSummaryResponse(BaseModel):
    id: UUID
    serial_number: str
    utility_meter_number: str | None = None
    current_status: str
    account_id: UUID | None = None
    account_number: str | None = None


class ServicePointLinkedSubscriberSummaryResponse(BaseModel):
    id: UUID
    full_name: str
    consumer_type: str
    account_id: UUID | None = None
    account_number: str | None = None
    account_status: str | None = None


class ServicePointDetailResponse(BaseModel):
    id: UUID
    service_point_code: str
    address_line: str | None = None
    premises_type: str | None = None
    is_active: bool
    latitude: float | None = None
    longitude: float | None = None
    linked_meter_count: int = Field(ge=0)
    linked_subscriber_count: int = Field(ge=0)
    linked_account_count: int = Field(ge=0)
    linked_meters: list[ServicePointLinkedMeterSummaryResponse]
    linked_subscribers: list[ServicePointLinkedSubscriberSummaryResponse]
