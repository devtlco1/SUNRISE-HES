from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.meters.models import Meter
from app.modules.readings.models import (
    LoadProfileChannel,
    LoadProfileInterval,
    MeterReading,
    MeterReadingBatch,
    MeterRegisterSnapshot,
)
from app.modules.readings.schemas import (
    IngestReadingBatchRequest,
    IngestReadingBatchResponse,
    LoadProfileChannelCreate,
    LoadProfileChannelListResponse,
    LoadProfileChannelResponse,
    LoadProfileChannelUpdate,
    LoadProfileIntervalListResponse,
    LoadProfileIntervalResponse,
    MeterReadingBatchListResponse,
    MeterReadingBatchResponse,
    MeterReadingListResponse,
    MeterReadingResponse,
    MeterRegisterSnapshotListResponse,
    MeterRegisterSnapshotResponse,
)


def list_meter_reading_batches(session: Session, *, meter_id: uuid.UUID, limit: int = 50) -> MeterReadingBatchListResponse:
    total = session.scalar(
        select(func.count()).select_from(MeterReadingBatch).where(MeterReadingBatch.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(MeterReadingBatch)
        .options(
            selectinload(MeterReadingBatch.readings),
            selectinload(MeterReadingBatch.register_snapshots),
        )
        .where(MeterReadingBatch.meter_id == meter_id)
        .order_by(MeterReadingBatch.captured_at.desc())
        .limit(limit)
    ).all()
    return MeterReadingBatchListResponse(total=total, items=[serialize_batch(item) for item in items])


def list_meter_readings(session: Session, *, meter_id: uuid.UUID, limit: int = 100) -> MeterReadingListResponse:
    total = session.scalar(
        select(func.count()).select_from(MeterReading).where(MeterReading.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(MeterReading)
        .where(MeterReading.meter_id == meter_id)
        .order_by(MeterReading.captured_at.desc())
        .limit(limit)
    ).all()
    return MeterReadingListResponse(total=total, items=[serialize_reading(item) for item in items])


def list_meter_register_snapshots(
    session: Session,
    *,
    meter_id: uuid.UUID,
    limit: int = 50,
) -> MeterRegisterSnapshotListResponse:
    total = session.scalar(
        select(func.count()).select_from(MeterRegisterSnapshot).where(MeterRegisterSnapshot.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(MeterRegisterSnapshot)
        .where(MeterRegisterSnapshot.meter_id == meter_id)
        .order_by(MeterRegisterSnapshot.captured_at.desc())
        .limit(limit)
    ).all()
    return MeterRegisterSnapshotListResponse(
        total=total,
        items=[serialize_register_snapshot(item) for item in items],
    )


def list_load_profile_channels(
    session: Session,
    *,
    meter_id: uuid.UUID,
) -> LoadProfileChannelListResponse:
    total = session.scalar(
        select(func.count()).select_from(LoadProfileChannel).where(LoadProfileChannel.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(LoadProfileChannel)
        .where(LoadProfileChannel.meter_id == meter_id)
        .order_by(LoadProfileChannel.channel_code.asc())
    ).all()
    return LoadProfileChannelListResponse(
        total=total,
        items=[serialize_load_profile_channel(item) for item in items],
    )


def create_load_profile_channel(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: LoadProfileChannelCreate,
) -> LoadProfileChannel:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    existing = session.scalar(
        select(LoadProfileChannel).where(
            LoadProfileChannel.meter_id == meter_id,
            func.lower(LoadProfileChannel.channel_code) == payload.channel_code.lower(),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Load profile channel code already exists for this meter.",
        )

    channel = LoadProfileChannel(
        meter_id=meter_id,
        channel_code=payload.channel_code.strip().lower(),
        obis_code=payload.obis_code.strip(),
        unit=payload.unit,
        interval_seconds=payload.interval_seconds,
        is_active=payload.is_active,
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


def update_load_profile_channel(
    session: Session,
    *,
    channel_id: uuid.UUID,
    payload: LoadProfileChannelUpdate,
) -> LoadProfileChannel:
    channel = session.get(LoadProfileChannel, channel_id)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load profile channel not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(channel, field, value)
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


def list_load_profile_intervals(
    session: Session,
    *,
    meter_id: uuid.UUID,
    limit: int = 200,
) -> LoadProfileIntervalListResponse:
    total = session.scalar(
        select(func.count()).select_from(LoadProfileInterval).where(LoadProfileInterval.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(LoadProfileInterval)
        .where(LoadProfileInterval.meter_id == meter_id)
        .order_by(LoadProfileInterval.interval_start.desc())
        .limit(limit)
    ).all()
    return LoadProfileIntervalListResponse(
        total=total,
        items=[serialize_load_profile_interval(item) for item in items],
    )


def ingest_reading_batch(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: IngestReadingBatchRequest,
    commit: bool = True,
    ignore_duplicate_intervals: bool = False,
) -> IngestReadingBatchResponse:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    batch = MeterReadingBatch(
        meter_id=meter_id,
        related_command_id=payload.related_command_id,
        related_attempt_id=payload.related_attempt_id,
        session_history_id=payload.session_history_id,
        source_type=payload.source_type,
        captured_at=payload.captured_at,
        received_at=payload.received_at or payload.captured_at,
        status=payload.status,
        reading_context=payload.reading_context,
        correlation_id=payload.correlation_id,
    )
    session.add(batch)
    session.flush()

    readings: list[MeterReading] = []
    for item in payload.readings:
        reading = MeterReading(
            batch_id=batch.id,
            meter_id=meter_id,
            obis_code=item.obis_code,
            reading_type=item.reading_type,
            value_numeric=item.value_numeric,
            value_text=item.value_text,
            value_timestamp=item.value_timestamp,
            unit=item.unit,
            quality=item.quality,
            captured_at=item.captured_at,
            metadata_json=item.metadata,
        )
        session.add(reading)
        readings.append(reading)

    snapshots: list[MeterRegisterSnapshot] = []
    for item in payload.register_snapshots:
        snapshot = MeterRegisterSnapshot(
            meter_id=meter_id,
            related_batch_id=batch.id,
            snapshot_type=item.snapshot_type,
            captured_at=item.captured_at,
            payload=item.payload,
            checksum=item.checksum,
        )
        session.add(snapshot)
        snapshots.append(snapshot)

    skipped_duplicate_interval_count = 0
    seen_interval_windows: set[tuple[uuid.UUID, object, object]] = set()
    for item in payload.load_profile_intervals:
        channel = session.get(LoadProfileChannel, item.channel_id)
        if channel is None or channel.meter_id != meter_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Load profile interval channel is invalid for this meter.",
            )
        interval_key = (item.channel_id, item.interval_start, item.interval_end)
        if ignore_duplicate_intervals:
            if interval_key in seen_interval_windows:
                skipped_duplicate_interval_count += 1
                continue
            existing_interval = session.scalar(
                select(LoadProfileInterval).where(
                    LoadProfileInterval.channel_id == item.channel_id,
                    LoadProfileInterval.interval_start == item.interval_start,
                    LoadProfileInterval.interval_end == item.interval_end,
                )
            )
            if existing_interval is not None:
                skipped_duplicate_interval_count += 1
                continue
            seen_interval_windows.add(interval_key)
        session.add(
            LoadProfileInterval(
                meter_id=meter_id,
                channel_id=item.channel_id,
                interval_start=item.interval_start,
                interval_end=item.interval_end,
                value_numeric=item.value_numeric,
                quality=item.quality,
                source_batch_id=batch.id,
            )
        )

    try:
        if commit:
            session.commit()
        else:
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate load profile interval window detected.",
        ) from exc

    if skipped_duplicate_interval_count and batch.reading_context is None:
        batch.reading_context = {}
    if skipped_duplicate_interval_count:
        batch.reading_context = {
            **(batch.reading_context or {}),
            "skipped_duplicate_interval_count": skipped_duplicate_interval_count,
        }
        session.add(batch)
        if commit:
            session.commit()
        else:
            session.flush()

    if commit:
        session.refresh(batch)
    batch = session.scalar(
        select(MeterReadingBatch)
        .options(
            selectinload(MeterReadingBatch.readings),
            selectinload(MeterReadingBatch.register_snapshots),
        )
        .where(MeterReadingBatch.id == batch.id)
    )
    return IngestReadingBatchResponse(batch=serialize_batch(batch))


def serialize_reading(item: MeterReading) -> MeterReadingResponse:
    return MeterReadingResponse(
        id=item.id,
        batch_id=item.batch_id,
        meter_id=item.meter_id,
        obis_code=item.obis_code,
        reading_type=item.reading_type,
        value_numeric=item.value_numeric,
        value_text=item.value_text,
        value_timestamp=item.value_timestamp,
        unit=item.unit,
        quality=item.quality,
        captured_at=item.captured_at,
        metadata=item.metadata_json,
    )


def serialize_register_snapshot(item: MeterRegisterSnapshot) -> MeterRegisterSnapshotResponse:
    return MeterRegisterSnapshotResponse(
        id=item.id,
        meter_id=item.meter_id,
        related_batch_id=item.related_batch_id,
        snapshot_type=item.snapshot_type,
        captured_at=item.captured_at,
        payload=item.payload,
        checksum=item.checksum,
    )


def serialize_batch(item: MeterReadingBatch) -> MeterReadingBatchResponse:
    return MeterReadingBatchResponse(
        id=item.id,
        meter_id=item.meter_id,
        related_command_id=item.related_command_id,
        related_attempt_id=item.related_attempt_id,
        session_history_id=item.session_history_id,
        source_type=item.source_type,
        captured_at=item.captured_at,
        received_at=item.received_at,
        status=item.status,
        reading_context=item.reading_context,
        correlation_id=item.correlation_id,
        readings=[serialize_reading(reading) for reading in item.readings],
        register_snapshots=[serialize_register_snapshot(snapshot) for snapshot in item.register_snapshots],
    )


def serialize_load_profile_channel(item: LoadProfileChannel) -> LoadProfileChannelResponse:
    return LoadProfileChannelResponse(
        id=item.id,
        meter_id=item.meter_id,
        channel_code=item.channel_code,
        obis_code=item.obis_code,
        unit=item.unit,
        interval_seconds=item.interval_seconds,
        is_active=item.is_active,
    )


def serialize_load_profile_interval(item: LoadProfileInterval) -> LoadProfileIntervalResponse:
    return LoadProfileIntervalResponse(
        id=item.id,
        meter_id=item.meter_id,
        channel_id=item.channel_id,
        interval_start=item.interval_start,
        interval_end=item.interval_end,
        value_numeric=item.value_numeric,
        quality=item.quality,
        source_batch_id=item.source_batch_id,
    )
