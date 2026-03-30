from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.events.schemas import MeterEventIngestionResponse
from app.modules.events.service import ingest_meter_events
from app.modules.readings.schemas import MeterReadingBatchResponse
from app.modules.readings.service import ingest_reading_batch
from app.runtime.normalization import to_meter_events_ingest_request, to_reading_batch_ingest_request
from app.runtime.contracts import RuntimeCommandResult


class RuntimeIngestionPersistenceResult(BaseModel):
    ingested_batch: MeterReadingBatchResponse | None = None
    ingested_events: list[MeterEventIngestionResponse] = Field(default_factory=list)
    persisted_interval_count: int = 0
    skipped_duplicate_interval_count: int = 0


def persist_runtime_result_telemetry(
    session: Session,
    *,
    meter_id,
    command_id,
    attempt_id,
    session_history_id,
    result: RuntimeCommandResult,
) -> RuntimeIngestionPersistenceResult:
    batch_response = None
    ingested_events: list[MeterEventIngestionResponse] = []
    persisted_interval_count = 0
    skipped_duplicate_interval_count = 0

    reading_batch_request = to_reading_batch_ingest_request(
        result,
        related_command_id=command_id,
        related_attempt_id=attempt_id,
        session_history_id=session_history_id,
    )
    if reading_batch_request is not None:
        batch_result = ingest_reading_batch(
            session,
            meter_id=meter_id,
            payload=reading_batch_request,
            commit=False,
            ignore_duplicate_intervals=True,
        )
        batch_response = batch_result.batch
        persisted_interval_count = len(reading_batch_request.load_profile_intervals)
        reading_context = batch_response.reading_context or {}
        skipped_duplicate_interval_count = int(reading_context.get("skipped_duplicate_interval_count", 0))
        persisted_interval_count -= skipped_duplicate_interval_count

    events_request = to_meter_events_ingest_request(
        result,
        related_batch_id=batch_response.id if batch_response is not None else None,
        related_attempt_id=attempt_id,
    )
    if events_request is not None:
        events_result = ingest_meter_events(
            session,
            meter_id=meter_id,
            payload=events_request,
            commit=False,
        )
        ingested_events = events_result.items

    return RuntimeIngestionPersistenceResult(
        ingested_batch=batch_response,
        ingested_events=ingested_events,
        persisted_interval_count=max(persisted_interval_count, 0),
        skipped_duplicate_interval_count=skipped_duplicate_interval_count,
    )
