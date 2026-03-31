from __future__ import annotations

from pydantic import BaseModel, Field

from uuid import UUID


class ConsumerListItemResponse(BaseModel):
    id: UUID
    full_name: str
    consumer_type: str
    external_ref: str | None = None
    national_id: str | None = None
    primary_account_number: str | None = None
    account_status_summary: str | None = None
    active_account_count: int = Field(ge=0)
    linked_meter_count: int = Field(ge=0)
    primary_service_point_code: str | None = None


class ConsumerListResponse(BaseModel):
    total: int
    items: list[ConsumerListItemResponse]


class ConsumerAccountSummaryResponse(BaseModel):
    id: UUID
    account_number: str
    status: str
    billing_cycle: str | None = None
    service_point_id: UUID | None = None
    service_point_code: str | None = None
    current_meter_count: int = Field(ge=0)


class ConsumerLinkedMeterSummaryResponse(BaseModel):
    id: UUID
    serial_number: str
    utility_meter_number: str | None = None
    current_status: str
    account_id: UUID | None = None
    account_number: str | None = None
    service_point_id: UUID | None = None
    service_point_code: str | None = None


class ConsumerDetailResponse(BaseModel):
    id: UUID
    full_name: str
    consumer_type: str
    external_ref: str | None = None
    national_id: str | None = None
    phone_number: str | None = None
    email: str | None = None
    account_status_summary: str | None = None
    active_account_count: int = Field(ge=0)
    linked_meter_count: int = Field(ge=0)
    accounts: list[ConsumerAccountSummaryResponse]
    linked_meters: list[ConsumerLinkedMeterSummaryResponse]


class MeterConsumerLinkageResponse(BaseModel):
    meter_id: UUID
    linkage_status: str
    linkage_source: str | None = None
    consumer_id: UUID | None = None
    consumer_display_name: str | None = None
    consumer_type: str | None = None
    consumer_external_ref: str | None = None
    account_id: UUID | None = None
    account_number: str | None = None
    account_status: str | None = None
    service_point_id: UUID | None = None
    service_point_code: str | None = None
