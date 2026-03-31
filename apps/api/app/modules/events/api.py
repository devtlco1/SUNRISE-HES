import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.auth.dependencies import require_permission
from app.modules.events.schemas import (
    IngestMeterEventsRequest,
    IngestMeterEventsResponse,
    MeterEventIngestionListResponse,
)
from app.modules.events.service import (
    ingest_meter_events,
    list_meter_ingested_events,
    list_recent_ingested_events,
)
from app.modules.jobs.dependencies import require_internal_api_token
from app.modules.users.models import User

events_router = APIRouter(prefix="/events", tags=["events"])
meter_events_router = APIRouter(prefix="/meters", tags=["meter-events"])
internal_meter_events_router = APIRouter(prefix="/internal/meters", tags=["internal-meter-events"])


@events_router.get("/recent", response_model=MeterEventIngestionListResponse)
def list_recent_ingested_events_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("events.read")),
) -> MeterEventIngestionListResponse:
    return list_recent_ingested_events(session, limit=limit)


@meter_events_router.get("/{meter_id}/ingested-events", response_model=MeterEventIngestionListResponse)
def list_meter_ingested_events_endpoint(
    meter_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("events.read")),
) -> MeterEventIngestionListResponse:
    return list_meter_ingested_events(session, meter_id=meter_id, limit=limit)


@internal_meter_events_router.post(
    "/{meter_id}/ingest-events",
    response_model=IngestMeterEventsResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def ingest_meter_events_endpoint(
    meter_id: uuid.UUID,
    payload: IngestMeterEventsRequest,
    session: Session = Depends(get_db_session),
) -> IngestMeterEventsResponse:
    return ingest_meter_events(session, meter_id=meter_id, payload=payload)
