from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class TransformerSubstationListItemResponse(BaseModel):
    id: UUID
    code: str
    name: str
    status: str
    feeder_code: str
    substation_id: UUID
    substation_code: str
    substation_name: str
    linked_meter_count: int = Field(ge=0)
    linked_service_point_count: int = Field(ge=0)
    primary_meter_serial_number: str | None = None
    primary_service_point_code: str | None = None
    location_hint: str | None = None


class TransformerSubstationListResponse(BaseModel):
    total: int
    items: list[TransformerSubstationListItemResponse]


class TransformerSubstationParentSummaryResponse(BaseModel):
    id: UUID
    code: str
    name: str
    status: str
    sector_code: str
    sector_name: str
    region_code: str
    region_name: str
    latitude: float | None = None
    longitude: float | None = None


class TransformerLinkedMeterSummaryResponse(BaseModel):
    id: UUID
    serial_number: str
    utility_meter_number: str | None = None
    current_status: str
    service_point_id: UUID | None = None
    service_point_code: str | None = None


class TransformerLinkedServicePointSummaryResponse(BaseModel):
    id: UUID
    service_point_code: str
    address_line: str | None = None
    premises_type: str | None = None
    is_active: bool


class TransformerSubstationDetailResponse(BaseModel):
    id: UUID
    code: str
    name: str
    status: str
    description: str | None = None
    feeder_code: str
    feeder_name: str
    latitude: float | None = None
    longitude: float | None = None
    substation: TransformerSubstationParentSummaryResponse
    linked_meter_count: int = Field(ge=0)
    linked_service_point_count: int = Field(ge=0)
    linked_meters: list[TransformerLinkedMeterSummaryResponse]
    linked_service_points: list[TransformerLinkedServicePointSummaryResponse]
