from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.consumers.models import ServicePoint
from app.modules.consumers.service import get_current_consumer_linkage_for_meter
from app.modules.gis.schemas import GisLiteEntityListResponse, GisLiteEntityResponse
from app.modules.meters.models import Meter


def list_gis_lite_entities(
    session: Session,
    *,
    limit: int = 50,
) -> GisLiteEntityListResponse:
    total = session.scalar(select(func.count()).select_from(Meter)) or 0
    meters = session.scalars(
        select(Meter).order_by(Meter.serial_number.asc(), Meter.id.asc()).limit(limit)
    ).all()
    if not meters:
        return GisLiteEntityListResponse(total=total, items=[])

    linkage_by_meter_id = {
        meter.id: get_current_consumer_linkage_for_meter(session, meter_id=meter.id)
        for meter in meters
    }
    service_point_ids = {
        service_point_id
        for service_point_id in [
            *[meter.service_point_id for meter in meters],
            *[linkage.service_point_id for linkage in linkage_by_meter_id.values()],
        ]
        if service_point_id is not None
    }

    service_points_by_id: dict[uuid.UUID, dict[str, object | None]] = {}
    if service_point_ids:
        rows = session.execute(
            select(
                ServicePoint.id,
                ServicePoint.service_point_code,
                ServicePoint.address_line,
                func.ST_Y(ServicePoint.geometry).label("latitude"),
                func.ST_X(ServicePoint.geometry).label("longitude"),
            ).where(ServicePoint.id.in_(service_point_ids))
        ).all()
        service_points_by_id = {
            row.id: {
                "service_point_code": row.service_point_code,
                "address_line": row.address_line,
                "latitude": float(row.latitude) if row.latitude is not None else None,
                "longitude": float(row.longitude) if row.longitude is not None else None,
            }
            for row in rows
        }

    items = [
        _serialize_gis_lite_entity(
            meter=meter,
            linkage=linkage_by_meter_id[meter.id],
            service_points_by_id=service_points_by_id,
        )
        for meter in meters
    ]
    return GisLiteEntityListResponse(total=total, items=items)


def _serialize_gis_lite_entity(
    *,
    meter: Meter,
    linkage,
    service_points_by_id: dict[uuid.UUID, dict[str, object | None]],
) -> GisLiteEntityResponse:
    service_point_id = meter.service_point_id or linkage.service_point_id
    service_point = (
        service_points_by_id.get(service_point_id)
        if service_point_id is not None
        else None
    )
    latitude = service_point.get("latitude") if service_point is not None else None
    longitude = service_point.get("longitude") if service_point is not None else None
    has_coordinates = latitude is not None and longitude is not None
    if has_coordinates:
        location_presence = "coordinates_available"
    elif service_point_id is not None:
        location_presence = "service_point_only"
    else:
        location_presence = "unlinked"

    return GisLiteEntityResponse(
        meter_id=meter.id,
        meter_serial_number=meter.serial_number,
        meter_status=meter.current_status.value,
        meter_last_seen_at=meter.last_seen_at,
        service_point_id=service_point_id,
        service_point_code=(
            service_point.get("service_point_code")
            if service_point is not None
            else linkage.service_point_code
        ),
        address_line=service_point.get("address_line") if service_point is not None else None,
        latitude=latitude,
        longitude=longitude,
        has_coordinates=has_coordinates,
        subscriber_id=linkage.consumer_id,
        subscriber_display_name=linkage.consumer_display_name,
        subscriber_type=linkage.consumer_type,
        account_id=linkage.account_id,
        account_number=linkage.account_number,
        location_presence=location_presence,
    )
