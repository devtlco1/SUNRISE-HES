from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.modules.consumers.models import ServicePoint
from app.modules.gis.models import Feeder, Region, Sector, Substation, Transformer
from app.modules.infrastructure.schemas import (
    TransformerLinkedMeterSummaryResponse,
    TransformerLinkedServicePointSummaryResponse,
    TransformerSubstationDetailResponse,
    TransformerSubstationListItemResponse,
    TransformerSubstationListResponse,
    TransformerSubstationParentSummaryResponse,
)
from app.modules.meters.models import Meter


@dataclass
class _TransformerRow:
    id: uuid.UUID
    code: str
    name: str
    status: str
    description: str | None
    feeder_code: str
    feeder_name: str
    substation_id: uuid.UUID
    substation_code: str
    substation_name: str
    substation_status: str
    sector_code: str
    sector_name: str
    region_code: str
    region_name: str
    latitude: float | None
    longitude: float | None
    substation_latitude: float | None
    substation_longitude: float | None


@dataclass
class _InfrastructureSupportData:
    meters_by_transformer: dict[uuid.UUID, list[Meter]]
    service_points_by_transformer: dict[uuid.UUID, list[ServicePoint]]
    service_points_by_id: dict[uuid.UUID, ServicePoint]


def list_transformer_substations(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> TransformerSubstationListResponse:
    filters = _build_transformer_search_filters(search)
    total_query = (
        select(func.count())
        .select_from(Transformer)
        .join(Feeder, Feeder.id == Transformer.feeder_id)
        .join(Substation, Substation.id == Feeder.substation_id)
        .join(Sector, Sector.id == Substation.sector_id)
        .join(Region, Region.id == Sector.region_id)
    )
    if filters:
        total_query = total_query.where(*filters)
    total = session.scalar(total_query) or 0

    statement = _build_transformer_statement()
    if filters:
        statement = statement.where(*filters)
    rows = session.execute(
        statement
        .order_by(Substation.code.asc(), Transformer.code.asc(), Transformer.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    if not rows:
        return TransformerSubstationListResponse(total=total, items=[])

    transformers = [_to_transformer_row(row) for row in rows]
    support = _load_infrastructure_supporting_data(
        session,
        transformer_ids=[transformer.id for transformer in transformers],
    )
    return TransformerSubstationListResponse(
        total=total,
        items=[
            _serialize_transformer_list_item(transformer=transformer, support=support)
            for transformer in transformers
        ],
    )


def get_transformer_substation_detail(
    session: Session,
    *,
    transformer_id: uuid.UUID,
) -> TransformerSubstationDetailResponse:
    row = session.execute(_build_transformer_statement().where(Transformer.id == transformer_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transformer not found.")

    transformer = _to_transformer_row(row)
    support = _load_infrastructure_supporting_data(session, transformer_ids=[transformer.id])
    linked_meters = _serialize_linked_meters(transformer.id, support=support)
    linked_service_points = _serialize_linked_service_points(transformer.id, support=support)
    return TransformerSubstationDetailResponse(
        id=transformer.id,
        code=transformer.code,
        name=transformer.name,
        status=transformer.status,
        description=transformer.description,
        feeder_code=transformer.feeder_code,
        feeder_name=transformer.feeder_name,
        latitude=transformer.latitude,
        longitude=transformer.longitude,
        substation=TransformerSubstationParentSummaryResponse(
            id=transformer.substation_id,
            code=transformer.substation_code,
            name=transformer.substation_name,
            status=transformer.substation_status,
            sector_code=transformer.sector_code,
            sector_name=transformer.sector_name,
            region_code=transformer.region_code,
            region_name=transformer.region_name,
            latitude=transformer.substation_latitude,
            longitude=transformer.substation_longitude,
        ),
        linked_meter_count=len(linked_meters),
        linked_service_point_count=len(linked_service_points),
        linked_meters=linked_meters,
        linked_service_points=linked_service_points,
    )


def _load_infrastructure_supporting_data(
    session: Session,
    *,
    transformer_ids: list[uuid.UUID],
) -> _InfrastructureSupportData:
    if not transformer_ids:
        return _InfrastructureSupportData({}, {}, {})

    meters = session.scalars(
        select(Meter)
        .where(Meter.transformer_id.in_(transformer_ids))
        .order_by(Meter.serial_number.asc(), Meter.id.asc())
    ).all()
    meters_by_transformer: dict[uuid.UUID, list[Meter]] = {}
    service_point_ids: set[uuid.UUID] = set()
    for meter in meters:
        if meter.transformer_id is not None:
            meters_by_transformer.setdefault(meter.transformer_id, []).append(meter)
        if meter.service_point_id is not None:
            service_point_ids.add(meter.service_point_id)

    service_points = session.scalars(
        select(ServicePoint)
        .where(ServicePoint.transformer_id.in_(transformer_ids))
        .order_by(ServicePoint.service_point_code.asc(), ServicePoint.id.asc())
    ).all()
    service_points_by_transformer: dict[uuid.UUID, list[ServicePoint]] = {}
    for service_point in service_points:
        if service_point.transformer_id is not None:
            service_points_by_transformer.setdefault(service_point.transformer_id, []).append(service_point)
        service_point_ids.add(service_point.id)

    service_points_by_id = (
        {
            service_point.id: service_point
            for service_point in session.scalars(
                select(ServicePoint)
                .where(ServicePoint.id.in_(service_point_ids))
                .order_by(ServicePoint.service_point_code.asc(), ServicePoint.id.asc())
            ).all()
        }
        if service_point_ids
        else {}
    )
    return _InfrastructureSupportData(
        meters_by_transformer=meters_by_transformer,
        service_points_by_transformer=service_points_by_transformer,
        service_points_by_id=service_points_by_id,
    )


def _serialize_transformer_list_item(
    *,
    transformer: _TransformerRow,
    support: _InfrastructureSupportData,
) -> TransformerSubstationListItemResponse:
    meters = support.meters_by_transformer.get(transformer.id, [])
    service_points = support.service_points_by_transformer.get(transformer.id, [])
    primary_service_point = service_points[0] if service_points else None
    return TransformerSubstationListItemResponse(
        id=transformer.id,
        code=transformer.code,
        name=transformer.name,
        status=transformer.status,
        feeder_code=transformer.feeder_code,
        substation_id=transformer.substation_id,
        substation_code=transformer.substation_code,
        substation_name=transformer.substation_name,
        linked_meter_count=len(meters),
        linked_service_point_count=len(service_points),
        primary_meter_serial_number=meters[0].serial_number if meters else None,
        primary_service_point_code=primary_service_point.service_point_code if primary_service_point else None,
        location_hint=primary_service_point.address_line if primary_service_point else transformer.substation_name,
    )


def _serialize_linked_meters(
    transformer_id: uuid.UUID,
    *,
    support: _InfrastructureSupportData,
) -> list[TransformerLinkedMeterSummaryResponse]:
    return [
        TransformerLinkedMeterSummaryResponse(
            id=meter.id,
            serial_number=meter.serial_number,
            utility_meter_number=meter.utility_meter_number,
            current_status=meter.current_status.value,
            service_point_id=meter.service_point_id,
            service_point_code=(
                support.service_points_by_id[meter.service_point_id].service_point_code
                if meter.service_point_id in support.service_points_by_id
                else None
            ),
        )
        for meter in support.meters_by_transformer.get(transformer_id, [])
    ]


def _serialize_linked_service_points(
    transformer_id: uuid.UUID,
    *,
    support: _InfrastructureSupportData,
) -> list[TransformerLinkedServicePointSummaryResponse]:
    return [
        TransformerLinkedServicePointSummaryResponse(
            id=service_point.id,
            service_point_code=service_point.service_point_code,
            address_line=service_point.address_line,
            premises_type=service_point.premises_type,
            is_active=service_point.is_active,
        )
        for service_point in support.service_points_by_transformer.get(transformer_id, [])
    ]


def _build_transformer_search_filters(search: str | None) -> list[object]:
    if search is None or not search.strip():
        return []
    search_term = f"%{search.strip().lower()}%"
    return [
        or_(
            func.lower(Transformer.code).like(search_term),
            func.lower(Transformer.name).like(search_term),
            func.lower(func.coalesce(Transformer.description, "")).like(search_term),
            func.lower(cast(Transformer.status, String)).like(search_term),
            func.lower(Feeder.code).like(search_term),
            func.lower(Feeder.name).like(search_term),
            func.lower(Substation.code).like(search_term),
            func.lower(Substation.name).like(search_term),
            func.lower(cast(Substation.status, String)).like(search_term),
            func.lower(Sector.code).like(search_term),
            func.lower(Sector.name).like(search_term),
            func.lower(Region.code).like(search_term),
            func.lower(Region.name).like(search_term),
        )
    ]


def _build_transformer_statement():
    return (
        select(
            Transformer.id,
            Transformer.code,
            Transformer.name,
            Transformer.status,
            Transformer.description,
            Feeder.code.label("feeder_code"),
            Feeder.name.label("feeder_name"),
            Substation.id.label("substation_id"),
            Substation.code.label("substation_code"),
            Substation.name.label("substation_name"),
            Substation.status.label("substation_status"),
            Sector.code.label("sector_code"),
            Sector.name.label("sector_name"),
            Region.code.label("region_code"),
            Region.name.label("region_name"),
            func.ST_Y(Transformer.location).label("latitude"),
            func.ST_X(Transformer.location).label("longitude"),
            func.ST_Y(Substation.location).label("substation_latitude"),
            func.ST_X(Substation.location).label("substation_longitude"),
        )
        .join(Feeder, Feeder.id == Transformer.feeder_id)
        .join(Substation, Substation.id == Feeder.substation_id)
        .join(Sector, Sector.id == Substation.sector_id)
        .join(Region, Region.id == Sector.region_id)
    )


def _to_transformer_row(row) -> _TransformerRow:
    return _TransformerRow(
        id=row.id,
        code=row.code,
        name=row.name,
        status=row.status.value,
        description=row.description,
        feeder_code=row.feeder_code,
        feeder_name=row.feeder_name,
        substation_id=row.substation_id,
        substation_code=row.substation_code,
        substation_name=row.substation_name,
        substation_status=row.substation_status.value,
        sector_code=row.sector_code,
        sector_name=row.sector_name,
        region_code=row.region_code,
        region_name=row.region_name,
        latitude=float(row.latitude) if row.latitude is not None else None,
        longitude=float(row.longitude) if row.longitude is not None else None,
        substation_latitude=float(row.substation_latitude) if row.substation_latitude is not None else None,
        substation_longitude=float(row.substation_longitude) if row.substation_longitude is not None else None,
    )
