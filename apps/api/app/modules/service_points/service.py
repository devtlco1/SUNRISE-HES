from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import Account
from app.modules.consumers.models import Consumer, MeterAccountAssignment, ServicePoint
from app.modules.meters.models import Meter
from app.modules.service_points.schemas import (
    ServicePointDetailResponse,
    ServicePointLinkedMeterSummaryResponse,
    ServicePointLinkedSubscriberSummaryResponse,
    ServicePointListItemResponse,
    ServicePointListResponse,
)


@dataclass
class _ServicePointLocation:
    id: uuid.UUID
    service_point_code: str
    address_line: str | None
    premises_type: str | None
    is_active: bool
    latitude: float | None
    longitude: float | None


def list_service_points(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> ServicePointListResponse:
    filters = _build_service_point_search_filters(search)
    total_query = select(func.count()).select_from(ServicePoint)
    if filters:
        total_query = total_query.where(*filters)
    total = session.scalar(total_query) or 0

    statement = _build_service_point_location_statement()
    if filters:
        statement = statement.where(*filters)
    service_points = session.execute(
        statement.order_by(ServicePoint.service_point_code.asc(), ServicePoint.id.asc()).offset(offset).limit(limit)
    ).all()
    if not service_points:
        return ServicePointListResponse(total=total, items=[])

    support = _load_service_point_supporting_data(
        session,
        service_point_ids=[row.id for row in service_points],
    )
    items = [
        _serialize_service_point_list_item(
            service_point=_to_service_point_location(row),
            support=support,
        )
        for row in service_points
    ]
    return ServicePointListResponse(total=total, items=items)


def get_service_point_detail(
    session: Session,
    *,
    service_point_id: uuid.UUID,
) -> ServicePointDetailResponse:
    row = session.execute(
        _build_service_point_location_statement().where(ServicePoint.id == service_point_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service point not found.")

    service_point = _to_service_point_location(row)
    support = _load_service_point_supporting_data(session, service_point_ids=[service_point.id])
    linked_meters = _build_linked_meter_summaries(service_point.id, support=support)
    linked_subscribers = _build_linked_subscriber_summaries(service_point.id, support=support)
    return ServicePointDetailResponse(
        id=service_point.id,
        service_point_code=service_point.service_point_code,
        address_line=service_point.address_line,
        premises_type=service_point.premises_type,
        is_active=service_point.is_active,
        latitude=service_point.latitude,
        longitude=service_point.longitude,
        linked_meter_count=len({meter.id for meter in linked_meters}),
        linked_subscriber_count=len({subscriber.id for subscriber in linked_subscribers}),
        linked_account_count=len(support.accounts_by_service_point.get(service_point.id, [])),
        linked_meters=linked_meters,
        linked_subscribers=linked_subscribers,
    )


@dataclass
class _ServicePointSupportData:
    accounts_by_service_point: dict[uuid.UUID, list[Account]]
    consumers_by_id: dict[uuid.UUID, Consumer]
    current_assignments_by_service_point: dict[uuid.UUID, list[MeterAccountAssignment]]
    current_assignments_by_account: dict[uuid.UUID, list[MeterAccountAssignment]]
    direct_meters_by_service_point: dict[uuid.UUID, list[Meter]]
    meters_by_id: dict[uuid.UUID, Meter]


def _load_service_point_supporting_data(
    session: Session,
    *,
    service_point_ids: list[uuid.UUID],
) -> _ServicePointSupportData:
    if not service_point_ids:
        return _ServicePointSupportData({}, {}, {}, {}, {}, {})

    accounts = session.scalars(
        select(Account)
        .where(Account.service_point_id.in_(service_point_ids))
        .order_by(Account.account_number.asc(), Account.id.asc())
    ).all()
    accounts_by_service_point: dict[uuid.UUID, list[Account]] = {}
    for account in accounts:
        if account.service_point_id is not None:
            accounts_by_service_point.setdefault(account.service_point_id, []).append(account)

    consumer_ids = {account.consumer_id for account in accounts}
    consumers = (
        session.scalars(select(Consumer).where(Consumer.id.in_(consumer_ids))).all()
        if consumer_ids
        else []
    )
    consumers_by_id = {consumer.id: consumer for consumer in consumers}

    direct_meters = session.scalars(
        select(Meter)
        .where(Meter.service_point_id.in_(service_point_ids))
        .order_by(Meter.serial_number.asc(), Meter.id.asc())
    ).all()
    direct_meters_by_service_point: dict[uuid.UUID, list[Meter]] = {}
    for meter in direct_meters:
        if meter.service_point_id is not None:
            direct_meters_by_service_point.setdefault(meter.service_point_id, []).append(meter)

    current_assignments = session.scalars(
        select(MeterAccountAssignment)
        .where(
            MeterAccountAssignment.is_current.is_(True),
            or_(
                MeterAccountAssignment.service_point_id.in_(service_point_ids),
                MeterAccountAssignment.account_id.in_([account.id for account in accounts])
                if accounts
                else false(),
            ),
        )
        .order_by(MeterAccountAssignment.active_from.desc(), MeterAccountAssignment.id.asc())
    ).all()
    current_assignments_by_service_point: dict[uuid.UUID, list[MeterAccountAssignment]] = {}
    current_assignments_by_account: dict[uuid.UUID, list[MeterAccountAssignment]] = {}
    accounts_by_id = {account.id: account for account in accounts}
    for assignment in current_assignments:
        current_assignments_by_account.setdefault(assignment.account_id, []).append(assignment)
        service_point_id = assignment.service_point_id
        if service_point_id is None:
            account = accounts_by_id.get(assignment.account_id)
            service_point_id = account.service_point_id if account is not None else None
        if service_point_id is not None:
            current_assignments_by_service_point.setdefault(service_point_id, []).append(assignment)

    meter_ids = {meter.id for meter in direct_meters} | {assignment.meter_id for assignment in current_assignments}
    meters = (
        session.scalars(select(Meter).where(Meter.id.in_(meter_ids))).all()
        if meter_ids
        else []
    )
    meters_by_id = {meter.id: meter for meter in meters}
    return _ServicePointSupportData(
        accounts_by_service_point=accounts_by_service_point,
        consumers_by_id=consumers_by_id,
        current_assignments_by_service_point=current_assignments_by_service_point,
        current_assignments_by_account=current_assignments_by_account,
        direct_meters_by_service_point=direct_meters_by_service_point,
        meters_by_id=meters_by_id,
    )


def _serialize_service_point_list_item(
    *,
    service_point: _ServicePointLocation,
    support: _ServicePointSupportData,
) -> ServicePointListItemResponse:
    linked_meters = _build_linked_meter_summaries(service_point.id, support=support)
    linked_subscribers = _build_linked_subscriber_summaries(service_point.id, support=support)
    return ServicePointListItemResponse(
        id=service_point.id,
        service_point_code=service_point.service_point_code,
        address_line=service_point.address_line,
        premises_type=service_point.premises_type,
        is_active=service_point.is_active,
        latitude=service_point.latitude,
        longitude=service_point.longitude,
        linked_meter_count=len({meter.id for meter in linked_meters}),
        linked_subscriber_count=len({subscriber.id for subscriber in linked_subscribers}),
        linked_account_count=len(support.accounts_by_service_point.get(service_point.id, [])),
        primary_meter_serial_number=linked_meters[0].serial_number if linked_meters else None,
        primary_subscriber_display_name=linked_subscribers[0].full_name if linked_subscribers else None,
    )


def _build_linked_meter_summaries(
    service_point_id: uuid.UUID,
    *,
    support: _ServicePointSupportData,
) -> list[ServicePointLinkedMeterSummaryResponse]:
    items: list[ServicePointLinkedMeterSummaryResponse] = []
    seen_meter_ids: set[uuid.UUID] = set()

    for meter in support.direct_meters_by_service_point.get(service_point_id, []):
        if meter.id in seen_meter_ids:
            continue
        seen_meter_ids.add(meter.id)
        items.append(
            ServicePointLinkedMeterSummaryResponse(
                id=meter.id,
                serial_number=meter.serial_number,
                utility_meter_number=meter.utility_meter_number,
                current_status=meter.current_status.value,
            )
        )

    accounts_by_id = {
        account.id: account
        for account in support.accounts_by_service_point.get(service_point_id, [])
    }
    for assignment in support.current_assignments_by_service_point.get(service_point_id, []):
        meter = support.meters_by_id.get(assignment.meter_id)
        if meter is None or meter.id in seen_meter_ids:
            continue
        seen_meter_ids.add(meter.id)
        account = accounts_by_id.get(assignment.account_id)
        items.append(
            ServicePointLinkedMeterSummaryResponse(
                id=meter.id,
                serial_number=meter.serial_number,
                utility_meter_number=meter.utility_meter_number,
                current_status=meter.current_status.value,
                account_id=account.id if account is not None else None,
                account_number=account.account_number if account is not None else None,
            )
        )

    items.sort(key=lambda item: (item.serial_number, str(item.id)))
    return items


def _build_linked_subscriber_summaries(
    service_point_id: uuid.UUID,
    *,
    support: _ServicePointSupportData,
) -> list[ServicePointLinkedSubscriberSummaryResponse]:
    items: list[ServicePointLinkedSubscriberSummaryResponse] = []
    seen_consumer_ids: set[uuid.UUID] = set()
    for account in support.accounts_by_service_point.get(service_point_id, []):
        consumer = support.consumers_by_id.get(account.consumer_id)
        if consumer is None or consumer.id in seen_consumer_ids:
            continue
        seen_consumer_ids.add(consumer.id)
        items.append(
            ServicePointLinkedSubscriberSummaryResponse(
                id=consumer.id,
                full_name=consumer.full_name,
                consumer_type=consumer.consumer_type,
                account_id=account.id,
                account_number=account.account_number,
                account_status=account.status,
            )
        )
    items.sort(key=lambda item: (item.full_name, str(item.id)))
    return items


def _build_service_point_search_filters(search: str | None) -> list[object]:
    if search is None or not search.strip():
        return []
    search_term = f"%{search.strip().lower()}%"
    return [
        or_(
            func.lower(ServicePoint.service_point_code).like(search_term),
            func.lower(func.coalesce(ServicePoint.address_line, "")).like(search_term),
            func.lower(func.coalesce(ServicePoint.premises_type, "")).like(search_term),
        )
    ]


def _build_service_point_location_statement():
    return select(
        ServicePoint.id,
        ServicePoint.service_point_code,
        ServicePoint.address_line,
        ServicePoint.premises_type,
        ServicePoint.is_active,
        func.ST_Y(ServicePoint.geometry).label("latitude"),
        func.ST_X(ServicePoint.geometry).label("longitude"),
    )


def _to_service_point_location(row) -> _ServicePointLocation:
    return _ServicePointLocation(
        id=row.id,
        service_point_code=row.service_point_code,
        address_line=row.address_line,
        premises_type=row.premises_type,
        is_active=row.is_active,
        latitude=float(row.latitude) if row.latitude is not None else None,
        longitude=float(row.longitude) if row.longitude is not None else None,
    )
