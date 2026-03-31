from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.modules.accounts.models import Account
from app.modules.consumers.models import Consumer, MeterAccountAssignment, ServicePoint
from app.modules.meters.models import Meter
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_protocol_runtime_foundation import _create_meter_record


def _create_meter_consumer_linkage_fixture(
    client,
    db_session: Session,
) -> tuple[str, str, str]:
    token = _login_as_super_admin(client, db_session)
    suffix = uuid4().hex[:8]
    meter_id = _create_meter_record(client, token)
    meter = db_session.get(Meter, UUID(meter_id))
    assert meter is not None

    consumer = Consumer(
        full_name="Amina Al Balushi",
        consumer_type="residential",
        external_ref=f"CON-LINK-{suffix}",
        national_id=f"NID-LINK-{suffix}",
    )
    service_point = ServicePoint(
        service_point_code=f"SP-LINK-{suffix}",
        address_line="Muscat Heights",
        premises_type="villa",
        is_active=True,
    )
    db_session.add_all([consumer, service_point])
    db_session.flush()

    account = Account(
        consumer_id=consumer.id,
        service_point_id=service_point.id,
        account_number=f"ACC-LINK-{suffix}",
        status="active",
        billing_cycle="monthly",
    )
    db_session.add(account)
    db_session.flush()

    db_session.add(
        MeterAccountAssignment(
            meter_id=meter.id,
            account_id=account.id,
            service_point_id=service_point.id,
            active_from=date(2026, 1, 1),
            is_current=True,
        )
    )
    db_session.commit()
    return token, meter_id, str(consumer.id)


def test_meter_consumer_linkage_returns_current_linked_consumer_context(
    client,
    db_session: Session,
) -> None:
    token, meter_id, consumer_id = _create_meter_consumer_linkage_fixture(client, db_session)

    response = client.get(
        f"/api/v1/meters/{meter_id}/consumer-linkage",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meter_id"] == meter_id
    assert payload["linkage_status"] == "linked"
    assert payload["linkage_source"] == "meter_account_assignment"
    assert payload["consumer_id"] == consumer_id
    assert payload["consumer_display_name"] == "Amina Al Balushi"
    assert payload["account_number"].startswith("ACC-LINK-")
    assert payload["account_status"] == "active"
    assert payload["service_point_code"].startswith("SP-LINK-")


def test_meter_consumer_linkage_returns_unlinked_state_when_no_consumer_is_linked(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)

    response = client.get(
        f"/api/v1/meters/{meter_id}/consumer-linkage",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "meter_id": meter_id,
        "linkage_status": "unlinked",
        "linkage_source": None,
        "consumer_id": None,
        "consumer_display_name": None,
        "consumer_type": None,
        "consumer_external_ref": None,
        "account_id": None,
        "account_number": None,
        "account_status": None,
        "service_point_id": None,
        "service_point_code": None,
    }


def test_meter_consumer_linkage_returns_not_found_for_unknown_meter(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.get(
        "/api/v1/meters/00000000-0000-0000-0000-000000000999/consumer-linkage",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "meter not found" in response.json()["detail"].lower()
