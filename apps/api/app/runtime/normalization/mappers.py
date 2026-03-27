from __future__ import annotations

from uuid import UUID

from app.modules.events.schemas import IngestMeterEventsRequest, MeterEventIngestItem
from app.modules.readings.schemas import (
    IngestReadingBatchRequest,
    LoadProfileIntervalIngestItem,
    MeterReadingIngestItem,
    MeterRegisterSnapshotIngestItem,
)
from app.runtime.contracts import RuntimeCommandResult


def to_reading_batch_ingest_request(
    result: RuntimeCommandResult,
    *,
    related_command_id: UUID | None = None,
    related_attempt_id: UUID | None = None,
    session_history_id: UUID | None = None,
) -> IngestReadingBatchRequest | None:
    if result.reading_batch is None:
        return None

    batch = result.reading_batch
    return IngestReadingBatchRequest(
        related_command_id=related_command_id,
        related_attempt_id=related_attempt_id,
        session_history_id=session_history_id,
        source_type=batch.source_type,
        captured_at=batch.captured_at,
        received_at=batch.received_at,
        status=batch.status,
        reading_context=batch.reading_context,
        correlation_id=batch.correlation_id,
        readings=[
            MeterReadingIngestItem(**reading.model_dump()) for reading in batch.readings
        ],
        register_snapshots=[
            MeterRegisterSnapshotIngestItem(**snapshot.model_dump())
            for snapshot in batch.register_snapshots
        ],
        load_profile_intervals=[
            LoadProfileIntervalIngestItem(**interval.model_dump())
            for interval in batch.load_profile_intervals
        ],
    )


def to_meter_events_ingest_request(
    result: RuntimeCommandResult,
    *,
    related_batch_id: UUID | None = None,
    related_attempt_id: UUID | None = None,
) -> IngestMeterEventsRequest | None:
    if not result.events:
        return None

    return IngestMeterEventsRequest(
        related_batch_id=related_batch_id,
        related_attempt_id=related_attempt_id,
        received_at=result.session_result.ended_at if result.session_result else None,
        correlation_id=result.session_result.correlation_id if result.session_result else None,
        events=[MeterEventIngestItem(**event.model_dump()) for event in result.events],
    )


def to_command_result_summary(result: RuntimeCommandResult) -> dict[str, object]:
    return {
        "outcome": result.outcome.value,
        "latest_error_code": result.latest_error_code,
        "latest_error_message": result.latest_error_message,
        "has_readings": result.reading_batch is not None,
        "event_count": len(result.events),
        "session_status": result.session_result.status.value if result.session_result else None,
        "result_summary": result.result_summary,
    }
