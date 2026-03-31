from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import Account
from app.modules.consumers.models import Consumer, MeterAccountAssignment, ServicePoint
from app.modules.consumers.schemas import (
    ConsumerAccountSummaryResponse,
    ConsumerDetailResponse,
    ConsumerLinkedMeterSummaryResponse,
    ConsumerListItemResponse,
    ConsumerListResponse,
    MeterConsumerLinkageResponse,
)
from app.modules.meters.models import Meter


def list_consumers(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> ConsumerListResponse:
    filters = _build_consumer_search_filters(search)
    total_query = select(func.count()).select_from(Consumer)
    if filters:
        total_query = total_query.where(*filters)
    total = session.scalar(total_query) or 0

    consumer_query = select(Consumer).order_by(Consumer.full_name.asc(), Consumer.id.asc())
    if filters:
        consumer_query = consumer_query.where(*filters)
    consumers = session.scalars(consumer_query.offset(offset).limit(limit)).all()
    if not consumers:
        return ConsumerListResponse(total=total, items=[])

    accounts_by_consumer, assignments_by_account, service_points_by_id, _ = _load_consumer_supporting_data(
        session,
        consumer_ids=[consumer.id for consumer in consumers],
    )
    items = [
        _serialize_consumer_list_item(
            consumer=consumer,
            accounts=accounts_by_consumer.get(consumer.id, []),
            assignments_by_account=assignments_by_account,
            service_points_by_id=service_points_by_id,
        )
        for consumer in consumers
    ]
    return ConsumerListResponse(total=total, items=items)


def get_consumer_detail(session: Session, consumer_id: uuid.UUID) -> ConsumerDetailResponse:
    consumer = session.get(Consumer, consumer_id)
    if consumer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consumer not found.")

    accounts_by_consumer, assignments_by_account, service_points_by_id, meters_by_id = _load_consumer_supporting_data(
        session,
        consumer_ids=[consumer.id],
    )
    accounts = accounts_by_consumer.get(consumer.id, [])
    linked_meters = _serialize_linked_meters(
        accounts=accounts,
        assignments_by_account=assignments_by_account,
        service_points_by_id=service_points_by_id,
        meters_by_id=meters_by_id,
    )
    return ConsumerDetailResponse(
        id=consumer.id,
        full_name=consumer.full_name,
        consumer_type=consumer.consumer_type,
        external_ref=consumer.external_ref,
        national_id=consumer.national_id,
        phone_number=consumer.phone_number,
        email=consumer.email,
        account_status_summary=_build_account_status_summary(accounts),
        active_account_count=sum(1 for account in accounts if account.status == "active"),
        linked_meter_count=len({meter.id for meter in linked_meters}),
        accounts=[
            _serialize_consumer_account_summary(
                account=account,
                assignments=assignments_by_account.get(account.id, []),
                service_points_by_id=service_points_by_id,
            )
            for account in accounts
        ],
        linked_meters=linked_meters,
    )


def get_current_consumer_linkage_for_meter(
    session: Session,
    *,
    meter_id: uuid.UUID,
) -> MeterConsumerLinkageResponse:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    assignment = session.scalar(
        select(MeterAccountAssignment)
        .where(
            MeterAccountAssignment.meter_id == meter.id,
            MeterAccountAssignment.is_current.is_(True),
        )
        .order_by(MeterAccountAssignment.active_from.desc(), MeterAccountAssignment.id.desc())
    )
    if assignment is not None:
        account = session.get(Account, assignment.account_id)
        consumer = session.get(Consumer, account.consumer_id) if account is not None else None
        service_point = None
        if assignment.service_point_id is not None:
            service_point = session.get(ServicePoint, assignment.service_point_id)
        if service_point is None and account is not None and account.service_point_id is not None:
            service_point = session.get(ServicePoint, account.service_point_id)
        if account is not None and consumer is not None:
            return MeterConsumerLinkageResponse(
                meter_id=meter.id,
                linkage_status="linked",
                linkage_source="meter_account_assignment",
                consumer_id=consumer.id,
                consumer_display_name=consumer.full_name,
                consumer_type=consumer.consumer_type,
                consumer_external_ref=consumer.external_ref,
                account_id=account.id,
                account_number=account.account_number,
                account_status=account.status,
                service_point_id=service_point.id if service_point is not None else None,
                service_point_code=service_point.service_point_code if service_point is not None else None,
            )

    if meter.service_point_id is not None:
        fallback_account = session.scalar(
            select(Account)
            .where(Account.service_point_id == meter.service_point_id)
            .order_by(Account.created_at.asc(), Account.id.asc())
        )
        fallback_service_point = session.get(ServicePoint, meter.service_point_id)
        if fallback_account is not None:
            consumer = session.get(Consumer, fallback_account.consumer_id)
            if consumer is not None:
                return MeterConsumerLinkageResponse(
                    meter_id=meter.id,
                    linkage_status="linked",
                    linkage_source="meter_service_point",
                    consumer_id=consumer.id,
                    consumer_display_name=consumer.full_name,
                    consumer_type=consumer.consumer_type,
                    consumer_external_ref=consumer.external_ref,
                    account_id=fallback_account.id,
                    account_number=fallback_account.account_number,
                    account_status=fallback_account.status,
                    service_point_id=fallback_service_point.id
                    if fallback_service_point is not None
                    else None,
                    service_point_code=fallback_service_point.service_point_code
                    if fallback_service_point is not None
                    else None,
                )

    return MeterConsumerLinkageResponse(
        meter_id=meter.id,
        linkage_status="unlinked",
    )


def _build_consumer_search_filters(search: str | None) -> list[object]:
    if search is None or not search.strip():
        return []
    search_term = f"%{search.strip().lower()}%"
    return [
        or_(
            func.lower(Consumer.full_name).like(search_term),
            func.lower(func.coalesce(Consumer.external_ref, "")).like(search_term),
            func.lower(func.coalesce(Consumer.national_id, "")).like(search_term),
        )
    ]


def _load_consumer_supporting_data(
    session: Session,
    *,
    consumer_ids: list[uuid.UUID],
) -> tuple[
    dict[uuid.UUID, list[Account]],
    dict[uuid.UUID, list[MeterAccountAssignment]],
    dict[uuid.UUID, ServicePoint],
    dict[uuid.UUID, Meter],
]:
    if not consumer_ids:
        return {}, {}, {}, {}

    accounts = session.scalars(
        select(Account)
        .where(Account.consumer_id.in_(consumer_ids))
        .order_by(Account.account_number.asc(), Account.id.asc())
    ).all()
    accounts_by_consumer: dict[uuid.UUID, list[Account]] = {}
    for account in accounts:
        accounts_by_consumer.setdefault(account.consumer_id, []).append(account)

    account_ids = [account.id for account in accounts]
    assignments = (
        session.scalars(
            select(MeterAccountAssignment)
            .where(MeterAccountAssignment.account_id.in_(account_ids))
            .order_by(
                MeterAccountAssignment.is_current.desc(),
                MeterAccountAssignment.active_from.desc(),
                MeterAccountAssignment.id.asc(),
            )
        ).all()
        if account_ids
        else []
    )
    assignments_by_account: dict[uuid.UUID, list[MeterAccountAssignment]] = {}
    for assignment in assignments:
        assignments_by_account.setdefault(assignment.account_id, []).append(assignment)

    service_point_ids = {
        service_point_id
        for service_point_id in [
            *[account.service_point_id for account in accounts],
            *[assignment.service_point_id for assignment in assignments],
        ]
        if service_point_id is not None
    }
    service_points = (
        session.scalars(select(ServicePoint).where(ServicePoint.id.in_(service_point_ids))).all()
        if service_point_ids
        else []
    )
    service_points_by_id = {service_point.id: service_point for service_point in service_points}

    meter_ids = {assignment.meter_id for assignment in assignments}
    meters = (
        session.scalars(select(Meter).where(Meter.id.in_(meter_ids))).all()
        if meter_ids
        else []
    )
    meters_by_id = {meter.id: meter for meter in meters}
    return accounts_by_consumer, assignments_by_account, service_points_by_id, meters_by_id


def _serialize_consumer_list_item(
    *,
    consumer: Consumer,
    accounts: list[Account],
    assignments_by_account: dict[uuid.UUID, list[MeterAccountAssignment]],
    service_points_by_id: dict[uuid.UUID, ServicePoint],
) -> ConsumerListItemResponse:
    primary_account = _resolve_primary_account(accounts)
    linked_meter_ids = {
        assignment.meter_id
        for account in accounts
        for assignment in assignments_by_account.get(account.id, [])
        if assignment.is_current
    }
    primary_service_point_code = None
    if primary_account is not None:
        service_point = _resolve_account_service_point(
            account=primary_account,
            assignments=assignments_by_account.get(primary_account.id, []),
            service_points_by_id=service_points_by_id,
        )
        primary_service_point_code = service_point.service_point_code if service_point is not None else None
    return ConsumerListItemResponse(
        id=consumer.id,
        full_name=consumer.full_name,
        consumer_type=consumer.consumer_type,
        external_ref=consumer.external_ref,
        national_id=consumer.national_id,
        primary_account_number=primary_account.account_number if primary_account is not None else None,
        account_status_summary=_build_account_status_summary(accounts),
        active_account_count=sum(1 for account in accounts if account.status == "active"),
        linked_meter_count=len(linked_meter_ids),
        primary_service_point_code=primary_service_point_code,
    )


def _serialize_consumer_account_summary(
    *,
    account: Account,
    assignments: list[MeterAccountAssignment],
    service_points_by_id: dict[uuid.UUID, ServicePoint],
) -> ConsumerAccountSummaryResponse:
    service_point = _resolve_account_service_point(
        account=account,
        assignments=assignments,
        service_points_by_id=service_points_by_id,
    )
    return ConsumerAccountSummaryResponse(
        id=account.id,
        account_number=account.account_number,
        status=account.status,
        billing_cycle=account.billing_cycle,
        service_point_id=service_point.id if service_point is not None else None,
        service_point_code=service_point.service_point_code if service_point is not None else None,
        current_meter_count=len({assignment.meter_id for assignment in assignments if assignment.is_current}),
    )


def _serialize_linked_meters(
    *,
    accounts: list[Account],
    assignments_by_account: dict[uuid.UUID, list[MeterAccountAssignment]],
    service_points_by_id: dict[uuid.UUID, ServicePoint],
    meters_by_id: dict[uuid.UUID, Meter],
) -> list[ConsumerLinkedMeterSummaryResponse]:
    items: list[ConsumerLinkedMeterSummaryResponse] = []
    seen_meter_ids: set[uuid.UUID] = set()
    accounts_by_id = {account.id: account for account in accounts}
    for account in accounts:
        for assignment in assignments_by_account.get(account.id, []):
            if not assignment.is_current or assignment.meter_id in seen_meter_ids:
                continue
            meter = meters_by_id.get(assignment.meter_id)
            if meter is None:
                continue
            seen_meter_ids.add(assignment.meter_id)
            service_point = _resolve_assignment_service_point(
                assignment=assignment,
                account=accounts_by_id[account.id],
                service_points_by_id=service_points_by_id,
            )
            items.append(
                ConsumerLinkedMeterSummaryResponse(
                    id=meter.id,
                    serial_number=meter.serial_number,
                    utility_meter_number=meter.utility_meter_number,
                    current_status=meter.current_status.value,
                    account_id=account.id,
                    account_number=account.account_number,
                    service_point_id=service_point.id if service_point is not None else None,
                    service_point_code=service_point.service_point_code if service_point is not None else None,
                )
            )
    items.sort(key=lambda item: (item.serial_number, str(item.id)))
    return items


def _resolve_primary_account(accounts: list[Account]) -> Account | None:
    if not accounts:
        return None
    active_accounts = [account for account in accounts if account.status == "active"]
    return active_accounts[0] if active_accounts else accounts[0]


def _build_account_status_summary(accounts: list[Account]) -> str | None:
    unique_statuses = sorted({account.status for account in accounts if account.status})
    if not unique_statuses:
        return None
    if len(unique_statuses) == 1:
        return unique_statuses[0]
    return "mixed"


def _resolve_account_service_point(
    *,
    account: Account,
    assignments: list[MeterAccountAssignment],
    service_points_by_id: dict[uuid.UUID, ServicePoint],
) -> ServicePoint | None:
    if account.service_point_id is not None:
        service_point = service_points_by_id.get(account.service_point_id)
        if service_point is not None:
            return service_point
    for assignment in assignments:
        if assignment.service_point_id is None:
            continue
        service_point = service_points_by_id.get(assignment.service_point_id)
        if service_point is not None:
            return service_point
    return None


def _resolve_assignment_service_point(
    *,
    assignment: MeterAccountAssignment,
    account: Account,
    service_points_by_id: dict[uuid.UUID, ServicePoint],
) -> ServicePoint | None:
    if assignment.service_point_id is not None:
        service_point = service_points_by_id.get(assignment.service_point_id)
        if service_point is not None:
            return service_point
    if account.service_point_id is not None:
        return service_points_by_id.get(account.service_point_id)
    return None
