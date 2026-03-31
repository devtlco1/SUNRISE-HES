from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.modules.accounts.models import Account
from app.modules.consumers.models import Consumer, MeterAccountAssignment, ServicePoint
from app.modules.meters.models import Meter
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_protocol_runtime_foundation import _create_meter_record


def _create_consumer_fixture_graph(
    client,
    db_session: Session,
) -> tuple[str, str, str, str]:
    token = _login_as_super_admin(client, db_session)
    suffix = uuid4().hex[:8]
    meter_id_1 = _create_meter_record(client, token)
    meter_1 = db_session.get(Meter, UUID(meter_id_1))
    assert meter_1 is not None
    meter_2 = Meter(
        serial_number=f"SUBSCRIBER-METER-{suffix}",
        utility_meter_number=f"SUBSCRIBER-UMN-{suffix}",
        manufacturer_id=meter_1.manufacturer_id,
        meter_model_id=meter_1.meter_model_id,
        current_status=meter_1.current_status,
        is_active=True,
    )
    db_session.add(meter_2)
    db_session.flush()

    consumer = Consumer(
        full_name="Amina Al Balushi",
        consumer_type="residential",
        external_ref=f"CON-1001-{suffix}",
        national_id=f"NID-1001-{suffix}",
        phone_number="+96890000001",
        email="amina@example.com",
    )
    secondary_consumer = Consumer(
        full_name="Beacon Bakery LLC",
        consumer_type="commercial",
        external_ref=f"CON-1002-{suffix}",
        national_id=f"NID-1002-{suffix}",
    )
    service_point = ServicePoint(
        service_point_code=f"SP-1001-{suffix}",
        address_line="Muscat Heights",
        premises_type="villa",
        is_active=True,
    )
    secondary_service_point = ServicePoint(
        service_point_code=f"SP-1002-{suffix}",
        address_line="Industrial Park",
        premises_type="shop",
        is_active=True,
    )
    db_session.add_all([consumer, secondary_consumer, service_point, secondary_service_point])
    db_session.flush()

    account_1 = Account(
        consumer_id=consumer.id,
        service_point_id=service_point.id,
        account_number=f"ACC-1001-{suffix}",
        status="active",
        billing_cycle="monthly",
    )
    account_2 = Account(
        consumer_id=consumer.id,
        account_number=f"ACC-1002-{suffix}",
        status="inactive",
        billing_cycle="quarterly",
    )
    secondary_account = Account(
        consumer_id=secondary_consumer.id,
        service_point_id=secondary_service_point.id,
        account_number=f"ACC-2001-{suffix}",
        status="active",
        billing_cycle="monthly",
    )
    db_session.add_all([account_1, account_2, secondary_account])
    db_session.flush()

    db_session.add_all(
        [
            MeterAccountAssignment(
                meter_id=meter_1.id,
                account_id=account_1.id,
                service_point_id=service_point.id,
                active_from=date(2026, 1, 1),
                is_current=True,
            ),
            MeterAccountAssignment(
                meter_id=meter_2.id,
                account_id=account_2.id,
                active_from=date(2026, 2, 1),
                is_current=True,
            ),
        ]
    )
    db_session.commit()
    return token, str(consumer.id), str(secondary_consumer.id), suffix


def test_consumers_list_returns_compact_operational_consumer_rows(
    client,
    db_session: Session,
) -> None:
    token, consumer_id, secondary_consumer_id, suffix = _create_consumer_fixture_graph(
        client,
        db_session,
    )

    response = client.get(
        f"/api/v1/consumers?offset=0&limit=20&search={suffix}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    items_by_id = {item["id"]: item for item in payload["items"]}
    assert items_by_id[consumer_id]["full_name"] == "Amina Al Balushi"
    assert items_by_id[consumer_id]["primary_account_number"].startswith("ACC-1001-")
    assert items_by_id[consumer_id]["account_status_summary"] == "mixed"
    assert items_by_id[consumer_id]["linked_meter_count"] == 2
    assert items_by_id[consumer_id]["primary_service_point_code"].startswith("SP-1001-")
    assert items_by_id[secondary_consumer_id]["linked_meter_count"] == 0


def test_consumer_detail_returns_bounded_accounts_and_linked_meters(
    client,
    db_session: Session,
) -> None:
    token, consumer_id, _, _ = _create_consumer_fixture_graph(client, db_session)

    response = client.get(
        f"/api/v1/consumers/{consumer_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == consumer_id
    assert payload["full_name"] == "Amina Al Balushi"
    assert payload["account_status_summary"] == "mixed"
    assert payload["active_account_count"] == 1
    assert payload["linked_meter_count"] == 2
    assert payload["current_operational_meter"] is not None
    assert payload["current_operational_meter"]["id"] is not None
    assert payload["current_operational_meter"]["serial_number"]
    assert payload["current_operational_meter"]["account_number"].startswith("ACC-")
    assert len(payload["accounts"]) == 2
    assert payload["accounts"][0]["account_number"].startswith("ACC-1001-")
    assert payload["accounts"][0]["service_point_code"].startswith("SP-1001-")
    assert payload["accounts"][0]["current_meter_count"] == 1
    assert len(payload["linked_meters"]) == 2
    assert payload["linked_meters"][0]["account_number"].startswith("ACC-")


def test_consumers_list_returns_bounded_empty_state_when_no_records_exist(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.get(
        "/api/v1/consumers?search=definitely-no-subscriber-match",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"total": 0, "items": []}


def test_consumer_detail_returns_not_found_for_unknown_consumer(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.get(
        "/api/v1/consumers/00000000-0000-0000-0000-000000000999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "consumer not found" in response.json()["detail"].lower()
