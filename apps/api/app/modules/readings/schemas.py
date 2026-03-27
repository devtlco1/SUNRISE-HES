from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.readings.enums import (
    ReadingBatchStatus,
    ReadingQuality,
    ReadingSourceType,
    ReadingType,
    SnapshotType,
)


class MeterReadingResponse(BaseModel):
    id: UUID
    batch_id: UUID
    meter_id: UUID
    obis_code: str
    reading_type: ReadingType
    value_numeric: Decimal | None
    value_text: str | None
    value_timestamp: datetime | None
    unit: str | None
    quality: ReadingQuality | None
    captured_at: datetime
    metadata: dict[str, object] | None


class MeterReadingListResponse(BaseModel):
    total: int
    items: list[MeterReadingResponse]


class MeterRegisterSnapshotResponse(BaseModel):
    id: UUID
    meter_id: UUID
    related_batch_id: UUID
    snapshot_type: SnapshotType
    captured_at: datetime
    payload: dict[str, object]
    checksum: str | None


class MeterRegisterSnapshotListResponse(BaseModel):
    total: int
    items: list[MeterRegisterSnapshotResponse]


class MeterReadingBatchResponse(BaseModel):
    id: UUID
    meter_id: UUID
    related_command_id: UUID | None
    related_attempt_id: UUID | None
    session_history_id: UUID | None
    source_type: ReadingSourceType
    captured_at: datetime
    received_at: datetime
    status: ReadingBatchStatus
    reading_context: dict[str, object] | None
    correlation_id: str | None
    readings: list[MeterReadingResponse]
    register_snapshots: list[MeterRegisterSnapshotResponse]


class MeterReadingBatchListResponse(BaseModel):
    total: int
    items: list[MeterReadingBatchResponse]


class LoadProfileChannelCreate(BaseModel):
    channel_code: str = Field(min_length=1, max_length=64)
    obis_code: str = Field(min_length=1, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    interval_seconds: int = Field(ge=1)
    is_active: bool = True


class LoadProfileChannelUpdate(BaseModel):
    obis_code: str | None = Field(default=None, min_length=1, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    interval_seconds: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class LoadProfileChannelResponse(BaseModel):
    id: UUID
    meter_id: UUID
    channel_code: str
    obis_code: str
    unit: str | None
    interval_seconds: int
    is_active: bool


class LoadProfileChannelListResponse(BaseModel):
    total: int
    items: list[LoadProfileChannelResponse]


class LoadProfileIntervalResponse(BaseModel):
    id: UUID
    meter_id: UUID
    channel_id: UUID
    interval_start: datetime
    interval_end: datetime
    value_numeric: Decimal | None
    quality: ReadingQuality | None
    source_batch_id: UUID | None


class LoadProfileIntervalListResponse(BaseModel):
    total: int
    items: list[LoadProfileIntervalResponse]


class MeterReadingIngestItem(BaseModel):
    obis_code: str = Field(min_length=1, max_length=64)
    reading_type: ReadingType
    value_numeric: Decimal | None = None
    value_text: str | None = None
    value_timestamp: datetime | None = None
    unit: str | None = None
    quality: ReadingQuality | None = None
    captured_at: datetime
    metadata: dict[str, object] | None = None


class MeterRegisterSnapshotIngestItem(BaseModel):
    snapshot_type: SnapshotType
    captured_at: datetime
    payload: dict[str, object]
    checksum: str | None = None


class LoadProfileIntervalIngestItem(BaseModel):
    channel_id: UUID
    interval_start: datetime
    interval_end: datetime
    value_numeric: Decimal | None = None
    quality: ReadingQuality | None = None


class IngestReadingBatchRequest(BaseModel):
    related_command_id: UUID | None = None
    related_attempt_id: UUID | None = None
    session_history_id: UUID | None = None
    source_type: ReadingSourceType
    captured_at: datetime
    received_at: datetime | None = None
    status: ReadingBatchStatus = ReadingBatchStatus.RECEIVED
    reading_context: dict[str, object] | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    readings: list[MeterReadingIngestItem] = Field(default_factory=list)
    register_snapshots: list[MeterRegisterSnapshotIngestItem] = Field(default_factory=list)
    load_profile_intervals: list[LoadProfileIntervalIngestItem] = Field(default_factory=list)


class IngestReadingBatchResponse(BaseModel):
    batch: MeterReadingBatchResponse
