import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.service import record_audit_event
from app.modules.auth.dependencies import require_permission
from app.modules.jobs.dependencies import require_internal_api_token
from app.modules.readings.schemas import (
    IngestReadingBatchRequest,
    IngestReadingBatchResponse,
    LoadProfileChannelCreate,
    LoadProfileChannelListResponse,
    LoadProfileChannelResponse,
    LoadProfileChannelUpdate,
    LoadProfileIntervalListResponse,
    MeterReadingBatchListResponse,
    MeterReadingListResponse,
    MeterRegisterSnapshotListResponse,
)
from app.modules.readings.service import (
    create_load_profile_channel,
    ingest_reading_batch,
    list_load_profile_channels,
    list_load_profile_intervals,
    list_meter_reading_batches,
    list_meter_readings,
    list_meter_register_snapshots,
    serialize_load_profile_channel,
    update_load_profile_channel,
)
from app.modules.users.models import User

meter_readings_router = APIRouter(prefix="/meters", tags=["meter-readings"])
load_profile_channels_router = APIRouter(prefix="/load-profile-channels", tags=["load-profile-channels"])
internal_meter_ingestion_router = APIRouter(prefix="/internal/meters", tags=["internal-meter-ingestion"])


@meter_readings_router.get("/{meter_id}/reading-batches", response_model=MeterReadingBatchListResponse)
def list_meter_reading_batches_endpoint(
    meter_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("readings.read")),
) -> MeterReadingBatchListResponse:
    return list_meter_reading_batches(session, meter_id=meter_id, limit=limit)


@meter_readings_router.get("/{meter_id}/readings", response_model=MeterReadingListResponse)
def list_meter_readings_endpoint(
    meter_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("readings.read")),
) -> MeterReadingListResponse:
    return list_meter_readings(session, meter_id=meter_id, limit=limit)


@meter_readings_router.get("/{meter_id}/register-snapshots", response_model=MeterRegisterSnapshotListResponse)
def list_meter_register_snapshots_endpoint(
    meter_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("readings.read")),
) -> MeterRegisterSnapshotListResponse:
    return list_meter_register_snapshots(session, meter_id=meter_id, limit=limit)


@meter_readings_router.get("/{meter_id}/load-profile-channels", response_model=LoadProfileChannelListResponse)
def list_load_profile_channels_endpoint(
    meter_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("profiles.read")),
) -> LoadProfileChannelListResponse:
    return list_load_profile_channels(session, meter_id=meter_id)


@meter_readings_router.post(
    "/{meter_id}/load-profile-channels",
    response_model=LoadProfileChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_load_profile_channel_endpoint(
    meter_id: uuid.UUID,
    payload: LoadProfileChannelCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("profiles.write")),
) -> LoadProfileChannelResponse:
    channel = create_load_profile_channel(session, meter_id=meter_id, payload=payload)
    response = serialize_load_profile_channel(channel)
    record_audit_event(
        session,
        action="profiles.channels.create",
        resource_type="load_profile_channels",
        resource_id=channel.id,
        actor_user_id=current_user.id,
        description="Load profile channel created.",
        details={"meter_id": str(meter_id), "channel_code": channel.channel_code},
        request_context=request.state.request_audit_context,
    )
    return response


@load_profile_channels_router.patch("/{channel_id}", response_model=LoadProfileChannelResponse)
def update_load_profile_channel_endpoint(
    channel_id: uuid.UUID,
    payload: LoadProfileChannelUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("profiles.write")),
) -> LoadProfileChannelResponse:
    channel = update_load_profile_channel(session, channel_id=channel_id, payload=payload)
    response = serialize_load_profile_channel(channel)
    record_audit_event(
        session,
        action="profiles.channels.update",
        resource_type="load_profile_channels",
        resource_id=channel.id,
        actor_user_id=current_user.id,
        description="Load profile channel updated.",
        details=payload.model_dump(exclude_unset=True),
        request_context=request.state.request_audit_context,
    )
    return response


@meter_readings_router.get("/{meter_id}/load-profile-intervals", response_model=LoadProfileIntervalListResponse)
def list_load_profile_intervals_endpoint(
    meter_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("profiles.read")),
) -> LoadProfileIntervalListResponse:
    return list_load_profile_intervals(session, meter_id=meter_id, limit=limit)


@internal_meter_ingestion_router.post(
    "/{meter_id}/ingest-reading-batch",
    response_model=IngestReadingBatchResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def ingest_reading_batch_endpoint(
    meter_id: uuid.UUID,
    payload: IngestReadingBatchRequest,
    session: Session = Depends(get_db_session),
) -> IngestReadingBatchResponse:
    return ingest_reading_batch(session, meter_id=meter_id, payload=payload)
