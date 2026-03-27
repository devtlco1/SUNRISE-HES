from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.meters.enums import (
    AuthenticationMode,
    IPMode,
    MeterCategory,
    MeterLifecycleStatus,
    PhaseType,
    TransportType,
)


class MeterManufacturerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    code: str = Field(min_length=2, max_length=64)
    country: str | None = Field(default=None, max_length=128)
    website: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class MeterManufacturerResponse(BaseModel):
    id: UUID
    name: str
    code: str
    country: str | None
    website: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MeterManufacturerListResponse(BaseModel):
    total: int
    items: list[MeterManufacturerResponse]


class MeterModelCreate(BaseModel):
    manufacturer_id: UUID
    model_code: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=2, max_length=255)
    phase_type: PhaseType
    meter_category: MeterCategory
    dlms_capable: bool = False
    is_active: bool = True


class MeterModelResponse(BaseModel):
    id: UUID
    manufacturer_id: UUID
    manufacturer_code: str
    model_code: str
    display_name: str
    phase_type: PhaseType
    meter_category: MeterCategory
    dlms_capable: bool
    is_active: bool


class MeterModelListResponse(BaseModel):
    total: int
    items: list[MeterModelResponse]


class MeterFirmwareVersionCreate(BaseModel):
    meter_model_id: UUID
    version: str = Field(min_length=1, max_length=64)
    release_notes: str | None = None
    is_active: bool = True


class MeterFirmwareVersionResponse(BaseModel):
    id: UUID
    meter_model_id: UUID
    meter_model_code: str
    version: str
    release_notes: str | None
    is_active: bool


class MeterFirmwareVersionListResponse(BaseModel):
    total: int
    items: list[MeterFirmwareVersionResponse]


class CommunicationProfileCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    transport_type: TransportType
    ip_mode: IPMode | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    apn: str | None = Field(default=None, max_length=255)
    authentication_mode: AuthenticationMode | None = None
    protocol_settings: dict[str, object] | None = None
    is_active: bool = True


class CommunicationProfileResponse(BaseModel):
    id: UUID
    code: str
    name: str
    transport_type: TransportType
    ip_mode: IPMode | None
    port: int | None
    apn: str | None
    authentication_mode: AuthenticationMode | None
    protocol_settings: dict[str, object] | None
    is_active: bool


class CommunicationProfileListResponse(BaseModel):
    total: int
    items: list[CommunicationProfileResponse]


class MeterProfileCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    meter_model_id: UUID
    communication_profile_id: UUID | None = None
    protocol_family: str | None = Field(default=None, max_length=128)
    protocol_defaults: dict[str, object] | None = None
    description: str | None = None
    is_active: bool = True


class MeterProfileResponse(BaseModel):
    id: UUID
    code: str
    name: str
    meter_model_id: UUID
    meter_model_code: str
    communication_profile_id: UUID | None
    communication_profile_code: str | None
    protocol_family: str | None
    protocol_defaults: dict[str, object] | None
    description: str | None
    is_active: bool


class MeterProfileListResponse(BaseModel):
    total: int
    items: list[MeterProfileResponse]


class MeterCreate(BaseModel):
    serial_number: str = Field(min_length=2, max_length=128)
    utility_meter_number: str | None = Field(default=None, max_length=128)
    badge_number: str | None = Field(default=None, max_length=128)
    manufacturer_id: UUID
    meter_model_id: UUID
    firmware_version_id: UUID | None = None
    communication_profile_id: UUID | None = None
    meter_profile_id: UUID | None = None
    transformer_id: UUID | None = None
    service_point_id: UUID | None = None
    current_status: MeterLifecycleStatus = MeterLifecycleStatus.REGISTERED
    notes: str | None = None
    is_active: bool = True
    metadata_json: dict[str, object] | None = None


class MeterUpdate(BaseModel):
    utility_meter_number: str | None = Field(default=None, max_length=128)
    badge_number: str | None = Field(default=None, max_length=128)
    firmware_version_id: UUID | None = None
    communication_profile_id: UUID | None = None
    meter_profile_id: UUID | None = None
    transformer_id: UUID | None = None
    service_point_id: UUID | None = None
    notes: str | None = None
    is_active: bool | None = None
    metadata_json: dict[str, object] | None = None


class MeterStatusChangeRequest(BaseModel):
    new_status: MeterLifecycleStatus
    reason: str | None = None


class MeterStatusHistoryResponse(BaseModel):
    id: UUID
    previous_status: MeterLifecycleStatus | None
    new_status: MeterLifecycleStatus
    changed_by_user_id: UUID | None
    reason: str | None
    changed_at: datetime


class MeterResponse(BaseModel):
    id: UUID
    serial_number: str
    utility_meter_number: str | None
    badge_number: str | None
    manufacturer_id: UUID
    manufacturer_code: str
    meter_model_id: UUID
    meter_model_code: str
    firmware_version_id: UUID | None
    firmware_version: str | None
    communication_profile_id: UUID | None
    communication_profile_code: str | None
    meter_profile_id: UUID | None
    meter_profile_code: str | None
    current_status: MeterLifecycleStatus
    transformer_id: UUID | None
    service_point_id: UUID | None
    notes: str | None
    is_active: bool
    installed_at: datetime | None
    commissioned_at: datetime | None
    last_seen_at: datetime | None
    metadata_json: dict[str, object] | None


class MeterDetailResponse(MeterResponse):
    status_history: list[MeterStatusHistoryResponse]


class MeterListResponse(BaseModel):
    total: int
    items: list[MeterResponse]
