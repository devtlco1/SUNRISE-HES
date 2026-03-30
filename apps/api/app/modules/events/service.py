from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.events.models import MeterEventIngestion
from app.modules.events.schemas import (
    IngestMeterEventsRequest,
    IngestMeterEventsResponse,
    MeterEventIngestionListResponse,
    MeterEventIngestionResponse,
)
from app.modules.meters.models import Meter


def list_meter_ingested_events(
    session: Session,
    *,
    meter_id: uuid.UUID,
    limit: int = 100,
) -> MeterEventIngestionListResponse:
    total = session.scalar(
        select(func.count()).select_from(MeterEventIngestion).where(MeterEventIngestion.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(MeterEventIngestion)
        .where(MeterEventIngestion.meter_id == meter_id)
        .order_by(MeterEventIngestion.occurred_at.desc())
        .limit(limit)
    ).all()
    return MeterEventIngestionListResponse(
        total=total,
        items=[serialize_ingested_event(item) for item in items],
    )


def ingest_meter_events(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: IngestMeterEventsRequest,
    commit: bool = True,
) -> IngestMeterEventsResponse:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    items: list[MeterEventIngestion] = []
    for event in payload.events:
        item = MeterEventIngestion(
            meter_id=meter_id,
            related_batch_id=payload.related_batch_id,
            related_attempt_id=payload.related_attempt_id,
            event_code=event.event_code,
            event_name=event.event_name,
            severity=event.severity,
            event_state=event.event_state,
            occurred_at=event.occurred_at,
            received_at=payload.received_at or event.occurred_at,
            raw_payload=event.raw_payload,
            normalized_payload=event.normalized_payload,
            correlation_id=payload.correlation_id,
        )
        session.add(item)
        items.append(item)
    if commit:
        session.commit()
        for item in items:
            session.refresh(item)
    else:
        session.flush()
    return IngestMeterEventsResponse(
        total_ingested=len(items),
        items=[serialize_ingested_event(item) for item in items],
    )


def serialize_ingested_event(item: MeterEventIngestion) -> MeterEventIngestionResponse:
    return MeterEventIngestionResponse(
        id=item.id,
        meter_id=item.meter_id,
        related_batch_id=item.related_batch_id,
        related_attempt_id=item.related_attempt_id,
        event_code=item.event_code,
        event_name=item.event_name,
        severity=item.severity,
        event_state=item.event_state,
        occurred_at=item.occurred_at,
        received_at=item.received_at,
        raw_payload=item.raw_payload,
        normalized_payload=item.normalized_payload,
        correlation_id=item.correlation_id,
    )
