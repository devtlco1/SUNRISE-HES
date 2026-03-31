from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class AccountLinkedMeterSummaryResponse(BaseModel):
    id: UUID
    serial_number: str
    utility_meter_number: str | None = None
    current_status: str


class AccountSubscriberSummaryResponse(BaseModel):
    id: UUID
    full_name: str
    consumer_type: str
    external_ref: str | None = None


class AccountServicePointSummaryResponse(BaseModel):
    id: UUID
    service_point_code: str
    address_line: str | None = None
    premises_type: str | None = None


class AccountListItemResponse(BaseModel):
    id: UUID
    account_number: str
    status: str
    billing_cycle: str | None = None
    subscriber_id: UUID
    subscriber_display_name: str
    service_point_id: UUID | None = None
    service_point_code: str | None = None
    linked_meter_count: int = Field(ge=0)
    primary_meter_serial_number: str | None = None


class AccountListResponse(BaseModel):
    total: int
    items: list[AccountListItemResponse]


class AccountDetailResponse(BaseModel):
    id: UUID
    account_number: str
    status: str
    billing_cycle: str | None = None
    subscriber: AccountSubscriberSummaryResponse
    service_point: AccountServicePointSummaryResponse | None = None
    linked_meter_count: int = Field(ge=0)
    linked_meters: list[AccountLinkedMeterSummaryResponse]
