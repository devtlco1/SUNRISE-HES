from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.modules.connectivity.enums import ConnectivitySessionPurpose, ConnectivitySessionStatus
from app.modules.events.enums import EventSeverity, EventState
from app.modules.readings.enums import (
    ReadingBatchStatus,
    ReadingQuality,
    ReadingSourceType,
    ReadingType,
    SnapshotType,
)


class RuntimeCommandOutcome(StringEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class RuntimeReadingPayload(BaseModel):
    obis_code: str = Field(min_length=1, max_length=64)
    reading_type: ReadingType
    value_numeric: Decimal | None = None
    value_text: str | None = None
    value_timestamp: datetime | None = None
    unit: str | None = None
    quality: ReadingQuality | None = None
    captured_at: datetime
    metadata: dict[str, object] | None = None


class RuntimeRegisterSnapshotPayload(BaseModel):
    snapshot_type: SnapshotType
    captured_at: datetime
    payload: dict[str, object]
    checksum: str | None = Field(default=None, max_length=128)


class RuntimeLoadProfileIntervalPayload(BaseModel):
    channel_id: UUID
    interval_start: datetime
    interval_end: datetime
    value_numeric: Decimal | None = None
    quality: ReadingQuality | None = None


class RuntimeReadingBatchPayload(BaseModel):
    source_type: ReadingSourceType
    captured_at: datetime
    received_at: datetime | None = None
    status: ReadingBatchStatus = ReadingBatchStatus.RECEIVED
    reading_context: dict[str, object] | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    readings: list[RuntimeReadingPayload] = Field(default_factory=list)
    register_snapshots: list[RuntimeRegisterSnapshotPayload] = Field(default_factory=list)
    load_profile_intervals: list[RuntimeLoadProfileIntervalPayload] = Field(default_factory=list)


class RuntimeEventPayload(BaseModel):
    event_code: str = Field(min_length=1, max_length=128)
    event_name: str | None = Field(default=None, max_length=255)
    severity: EventSeverity
    event_state: EventState
    occurred_at: datetime
    raw_payload: dict[str, object] | None = None
    normalized_payload: dict[str, object] | None = None


class RuntimeSessionResult(BaseModel):
    status: ConnectivitySessionStatus
    session_purpose: ConnectivitySessionPurpose
    started_at: datetime
    ended_at: datetime | None = None
    request_id: str | None = Field(default=None, max_length=128)
    correlation_id: str | None = Field(default=None, max_length=128)
    handshake_stage: str | None = Field(default=None, max_length=128)
    bytes_sent: int | None = Field(default=None, ge=0)
    bytes_received: int | None = Field(default=None, ge=0)
    transport_latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = None
    metadata: dict[str, object] | None = None


class RuntimeCommandResult(BaseModel):
    outcome: RuntimeCommandOutcome
    result_summary: dict[str, object] | None = None
    response_snapshot: dict[str, object] | None = None
    latest_error_code: str | None = Field(default=None, max_length=128)
    latest_error_message: str | None = None
    session_result: RuntimeSessionResult | None = None
    reading_batch: RuntimeReadingBatchPayload | None = None
    events: list[RuntimeEventPayload] = Field(default_factory=list)
