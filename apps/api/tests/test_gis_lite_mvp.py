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


def test_gis_lite_entities_return_bounded_location_and_linkage_context(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    meter = db_session.get(Meter, meter_id)
    assert meter is not None

    suffix = uuid4().hex[:8]
    service_point = ServicePoint(
        service_point_code=f"SP-GIS-{suffix}",
        address_line="Muscat Block 1",
        premises_type="residential",
        geometry=WKTElement("POINT(58.3829 23.5880)", srid=4326),
    )
    consumer = Consumer(
        full_name="Amina GIS",
        consumer_type="residential",
        external_ref=f"GIS-CONS-{suffix}",
    )
    db_session.add_all([service_point, consumer])
    db_session.flush()

    account = Account(
        consumer_id=consumer.id,
        service_point_id=service_point.id,
        account_number=f"ACC-GIS-{suffix}",
        status="active",
        billing_cycle="monthly",
    )
    db_session.add(account)
    db_session.flush()

    assignment = MeterAccountAssignment(
        meter_id=meter.id,
        account_id=account.id,
        service_point_id=service_point.id,
        active_from=date(2026, 3, 1),
        is_current=True,
    )
    meter.service_point_id = service_point.id
    db_session.add_all([assignment, meter])
    db_session.commit()

    response = client.get(
        "/api/v1/gis-lite/entities?limit=20",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    item = next(entry for entry in payload["items"] if entry["meter_id"] == meter_id)
    assert payload["total"] >= 1
    assert item["meter_serial_number"].startswith("RUNTIME-METER-")
    assert item["service_point_code"].startswith("SP-GIS-")
    assert item["address_line"] == "Muscat Block 1"
    assert item["has_coordinates"] is True
    assert item["location_presence"] == "coordinates_available"
    assert item["subscriber_display_name"] == "Amina GIS"
    assert item["account_number"].startswith("ACC-GIS-")


def test_gis_lite_entities_surface_unlinked_location_gaps_without_failing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)

    response = client.get(
        "/api/v1/gis-lite/entities?limit=50",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    item = next(entry for entry in response.json()["items"] if entry["meter_id"] == meter_id)
    assert item["has_coordinates"] is False
    assert item["location_presence"] == "unlinked"
    assert item["subscriber_id"] is None


def test_gis_lite_entities_respect_bounded_limit(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    _create_meter_record(client, token)
    _create_meter_record(client, token)

    response = client.get(
        "/api/v1/gis-lite/entities?limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
