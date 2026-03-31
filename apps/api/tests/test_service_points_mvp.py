from __future__ import annotations

from datetime import date
from uuid import uuid4

from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.modules.accounts.models import Account
from app.modules.consumers.models import Consumer, MeterAccountAssignment, ServicePoint
from app.modules.meters.models import Meter
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_protocol_runtime_foundation import _create_meter_record


def _create_service_point_fixture_graph(
    client,
    db_session: Session,
) -> tuple[str, str, str, str]:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    meter = db_session.get(Meter, meter_id)
    assert meter is not None

    suffix = uuid4().hex[:8]
    service_point = ServicePoint(
        service_point_code=f"SP-PREM-{suffix}",
        address_line="Muttrah Waterfront",
        premises_type="commercial",
        geometry=WKTElement("POINT(58.5900 23.6200)", srid=4326),
    )
    consumer = Consumer(
        full_name="Beacon Premises LLC",
        consumer_type="commercial",
        external_ref=f"PREM-CONS-{suffix}",
    )
    db_session.add_all([service_point, consumer])
    db_session.flush()

    account = Account(
        consumer_id=consumer.id,
        service_point_id=service_point.id,
        account_number=f"ACC-PREM-{suffix}",
        status="active",
        billing_cycle="monthly",
    )
    db_session.add(account)
    db_session.flush()

    assignment = MeterAccountAssignment(
        meter_id=meter.id,
        account_id=account.id,
        service_point_id=service_point.id,
        active_from=date(2026, 4, 1),
        is_current=True,
    )
    meter.service_point_id = service_point.id
    db_session.add_all([assignment, meter])
    db_session.commit()
    return token, str(service_point.id), meter_id, str(consumer.id)


def test_service_points_list_returns_compact_premise_visibility(
    client,
    db_session: Session,
) -> None:
    token, service_point_id, meter_id, consumer_id = _create_service_point_fixture_graph(
        client,
        db_session,
    )

    response = client.get(
        "/api/v1/service-points?offset=0&limit=20&search=SP-PREM",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    item = next(entry for entry in payload["items"] if entry["id"] == service_point_id)
    assert payload["total"] >= 1
    assert item["service_point_code"].startswith("SP-PREM-")
    assert item["linked_meter_count"] >= 1
    assert item["linked_subscriber_count"] >= 1
    assert item["linked_account_count"] >= 1
    assert item["primary_meter_serial_number"]
    assert item["primary_subscriber_display_name"] == "Beacon Premises LLC"


def test_service_point_detail_returns_bounded_linked_meter_and_subscriber_context(
    client,
    db_session: Session,
) -> None:
    token, service_point_id, meter_id, consumer_id = _create_service_point_fixture_graph(
        client,
        db_session,
    )

    response = client.get(
        f"/api/v1/service-points/{service_point_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == service_point_id
    assert payload["address_line"] == "Muttrah Waterfront"
    assert payload["premises_type"] == "commercial"
    assert payload["latitude"] is not None
    assert payload["longitude"] is not None
    assert payload["linked_meter_count"] >= 1
    assert payload["linked_subscriber_count"] >= 1
    assert payload["linked_meters"][0]["id"] == meter_id
    assert payload["linked_subscribers"][0]["id"] == consumer_id
    assert payload["linked_subscribers"][0]["account_status"] == "active"


def test_service_point_detail_returns_not_found_for_unknown_service_point(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.get(
        "/api/v1/service-points/00000000-0000-0000-0000-000000000001",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service point not found."
