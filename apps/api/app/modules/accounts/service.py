from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import Account
from app.modules.accounts.schemas import (
    AccountDetailResponse,
    AccountLinkedMeterSummaryResponse,
    AccountListItemResponse,
    AccountListResponse,
    AccountServicePointSummaryResponse,
    AccountSubscriberSummaryResponse,
)
from app.modules.consumers.models import Consumer, MeterAccountAssignment, ServicePoint
from app.modules.meters.models import Meter


def list_accounts(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> AccountListResponse:
    filters = _build_account_search_filters(search)
    total_query = select(func.count()).select_from(Account).join(
        Consumer, Consumer.id == Account.consumer_id
    )
    if filters:
        total_query = total_query.where(*filters)
    total = session.scalar(total_query) or 0

    statement = select(Account).order_by(Account.account_number.asc(), Account.id.asc())
    if filters:
        statement = statement.join(Consumer, Consumer.id == Account.consumer_id).where(*filters)
    accounts = session.scalars(statement.offset(offset).limit(limit)).all()
    if not accounts:
        return AccountListResponse(total=total, items=[])

    support = _load_account_supporting_data(
        session,
        accounts=accounts,
    )
    return AccountListResponse(
        total=total,
        items=[
            _serialize_account_list_item(account=account, support=support)
            for account in accounts
        ],
    )


def get_account_detail(
    session: Session,
    *,
    account_id: uuid.UUID,
) -> AccountDetailResponse:
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    support = _load_account_supporting_data(session, accounts=[account])
    return _serialize_account_detail(account=account, support=support)


class _AccountSupportData:
    def __init__(
        self,
        *,
        consumers_by_id: dict[uuid.UUID, Consumer],
        service_points_by_id: dict[uuid.UUID, ServicePoint],
        current_assignments_by_account: dict[uuid.UUID, list[MeterAccountAssignment]],
        meters_by_id: dict[uuid.UUID, Meter],
    ) -> None:
        self.consumers_by_id = consumers_by_id
        self.service_points_by_id = service_points_by_id
        self.current_assignments_by_account = current_assignments_by_account
        self.meters_by_id = meters_by_id


def _load_account_supporting_data(
    session: Session,
    *,
    accounts: list[Account],
) -> _AccountSupportData:
    consumer_ids = {account.consumer_id for account in accounts}
    service_point_ids = {
        account.service_point_id for account in accounts if account.service_point_id is not None
    }
    account_ids = [account.id for account in accounts]

    current_assignments = (
        session.scalars(
            select(MeterAccountAssignment)
            .where(
                MeterAccountAssignment.account_id.in_(account_ids),
                MeterAccountAssignment.is_current.is_(True),
            )
            .order_by(
                MeterAccountAssignment.active_from.desc(),
                MeterAccountAssignment.id.asc(),
            )
        ).all()
        if account_ids
        else []
    )
    current_assignments_by_account: dict[uuid.UUID, list[MeterAccountAssignment]] = {}
    meter_ids: set[uuid.UUID] = set()
    for assignment in current_assignments:
        current_assignments_by_account.setdefault(assignment.account_id, []).append(assignment)
        meter_ids.add(assignment.meter_id)
        if assignment.service_point_id is not None:
            service_point_ids.add(assignment.service_point_id)

    consumers = (
        session.scalars(select(Consumer).where(Consumer.id.in_(consumer_ids))).all()
        if consumer_ids
        else []
    )
    service_points = (
        session.scalars(select(ServicePoint).where(ServicePoint.id.in_(service_point_ids))).all()
        if service_point_ids
        else []
    )
    meters = (
        session.scalars(select(Meter).where(Meter.id.in_(meter_ids))).all()
        if meter_ids
        else []
    )
    return _AccountSupportData(
        consumers_by_id={consumer.id: consumer for consumer in consumers},
        service_points_by_id={service_point.id: service_point for service_point in service_points},
        current_assignments_by_account=current_assignments_by_account,
        meters_by_id={meter.id: meter for meter in meters},
    )


def _serialize_account_list_item(
    *,
    account: Account,
    support: _AccountSupportData,
) -> AccountListItemResponse:
    consumer = support.consumers_by_id[account.consumer_id]
    linked_meters = _serialize_linked_meters(account=account, support=support)
    service_point = _resolve_service_point(account=account, support=support)
    return AccountListItemResponse(
        id=account.id,
        account_number=account.account_number,
        status=account.status,
        billing_cycle=account.billing_cycle,
        subscriber_id=consumer.id,
        subscriber_display_name=consumer.full_name,
        service_point_id=service_point.id if service_point is not None else None,
        service_point_code=service_point.service_point_code if service_point is not None else None,
        linked_meter_count=len({meter.id for meter in linked_meters}),
        primary_meter_serial_number=linked_meters[0].serial_number if linked_meters else None,
    )


def _serialize_account_detail(
    *,
    account: Account,
    support: _AccountSupportData,
) -> AccountDetailResponse:
    consumer = support.consumers_by_id[account.consumer_id]
    service_point = _resolve_service_point(account=account, support=support)
    linked_meters = _serialize_linked_meters(account=account, support=support)
    return AccountDetailResponse(
        id=account.id,
        account_number=account.account_number,
        status=account.status,
        billing_cycle=account.billing_cycle,
        subscriber=AccountSubscriberSummaryResponse(
            id=consumer.id,
            full_name=consumer.full_name,
            consumer_type=consumer.consumer_type,
            external_ref=consumer.external_ref,
        ),
        service_point=(
            AccountServicePointSummaryResponse(
                id=service_point.id,
                service_point_code=service_point.service_point_code,
                address_line=service_point.address_line,
                premises_type=service_point.premises_type,
            )
            if service_point is not None
            else None
        ),
        linked_meter_count=len({meter.id for meter in linked_meters}),
        linked_meters=linked_meters,
    )


def _serialize_linked_meters(
    *,
    account: Account,
    support: _AccountSupportData,
) -> list[AccountLinkedMeterSummaryResponse]:
    items: list[AccountLinkedMeterSummaryResponse] = []
    seen_meter_ids: set[uuid.UUID] = set()
    for assignment in support.current_assignments_by_account.get(account.id, []):
        meter = support.meters_by_id.get(assignment.meter_id)
        if meter is None or meter.id in seen_meter_ids:
            continue
        seen_meter_ids.add(meter.id)
        items.append(
            AccountLinkedMeterSummaryResponse(
                id=meter.id,
                serial_number=meter.serial_number,
                utility_meter_number=meter.utility_meter_number,
                current_status=meter.current_status.value,
            )
        )
    items.sort(key=lambda item: (item.serial_number, str(item.id)))
    return items


def _resolve_service_point(
    *,
    account: Account,
    support: _AccountSupportData,
) -> ServicePoint | None:
    if account.service_point_id is not None:
        service_point = support.service_points_by_id.get(account.service_point_id)
        if service_point is not None:
            return service_point
    for assignment in support.current_assignments_by_account.get(account.id, []):
        if assignment.service_point_id is None:
            continue
        service_point = support.service_points_by_id.get(assignment.service_point_id)
        if service_point is not None:
            return service_point
    return None


def _build_account_search_filters(search: str | None) -> list[object]:
    if search is None or not search.strip():
        return []
    search_term = f"%{search.strip().lower()}%"
    return [
        or_(
            func.lower(Account.account_number).like(search_term),
            func.lower(func.coalesce(Account.status, "")).like(search_term),
            func.lower(func.coalesce(Account.billing_cycle, "")).like(search_term),
            func.lower(Consumer.full_name).like(search_term),
        )
    ]
