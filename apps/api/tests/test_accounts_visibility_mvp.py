from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.modules.accounts.models import Account
from app.modules.consumers.models import Consumer, MeterAccountAssignment, ServicePoint
from app.modules.meters.models import Meter
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_protocol_runtime_foundation import _create_meter_record


def _create_account_fixture_graph(
    client,
    db_session: Session,
) -> tuple[str, str, str, str, str]:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    meter = db_session.get(Meter, meter_id)
    assert meter is not None

    suffix = uuid4().hex[:8]
    consumer = Consumer(
        full_name="Account Visibility LLC",
        consumer_type="commercial",
        external_ref=f"ACC-CONS-{suffix}",
    )
    service_point = ServicePoint(
        service_point_code=f"SP-ACC-{suffix}",
        address_line="Seeb Gate 3",
        premises_type="commercial",
    )
    db_session.add_all([consumer, service_point])
    db_session.flush()

    account = Account(
        consumer_id=consumer.id,
        service_point_id=service_point.id,
        account_number=f"ACC-1001-{suffix}",
        status="active",
        billing_cycle="monthly",
    )
    db_session.add(account)
    db_session.flush()

    assignment = MeterAccountAssignment(
        meter_id=meter.id,
        account_id=account.id,
        service_point_id=service_point.id,
        active_from=date(2026, 5, 1),
        is_current=True,
    )
    db_session.add(assignment)
    db_session.commit()
    return token, str(account.id), str(consumer.id), str(service_point.id), meter_id


def test_accounts_list_returns_compact_account_visibility(
    client,
    db_session: Session,
) -> None:
    token, account_id, consumer_id, service_point_id, meter_id = _create_account_fixture_graph(
        client,
        db_session,
    )

    response = client.get(
        "/api/v1/accounts?offset=0&limit=20&search=ACC-1001",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    item = next(entry for entry in payload["items"] if entry["id"] == account_id)
    assert payload["total"] >= 1
    assert item["account_number"].startswith("ACC-1001-")
    assert item["subscriber_id"] == consumer_id
    assert item["service_point_id"] == service_point_id
    assert item["linked_meter_count"] >= 1
    assert item["primary_meter_serial_number"]


def test_account_detail_returns_bounded_linked_context(
    client,
    db_session: Session,
) -> None:
    token, account_id, consumer_id, service_point_id, meter_id = _create_account_fixture_graph(
        client,
        db_session,
    )

    response = client.get(
        f"/api/v1/accounts/{account_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == account_id
    assert payload["subscriber"]["id"] == consumer_id
    assert payload["service_point"]["id"] == service_point_id
    assert payload["service_point"]["service_point_code"].startswith("SP-ACC-")
    assert payload["linked_meter_count"] >= 1
    assert payload["linked_meters"][0]["id"] == meter_id


def test_account_detail_returns_not_found_for_unknown_account(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.get(
        "/api/v1/accounts/00000000-0000-0000-0000-000000000001",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found."
