from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.meters.models import Meter, MeterManufacturer, MeterModel, MeterStatusHistory


def _login_as_super_admin(client, db_session: Session) -> str:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"
    bootstrap_access_control(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_create_manufacturer(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Landis+Gyr",
            "code": "landis-gyr",
            "country": "Switzerland",
            "website": "https://www.landisgyr.com",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["code"] == "landis-gyr"
    assert db_session.scalar(select(MeterManufacturer).where(MeterManufacturer.code == "landis-gyr")) is not None


def test_create_meter_model(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)

    manufacturer_response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Itron", "code": "itron", "country": "United States", "is_active": True},
    )
    manufacturer_id = manufacturer_response.json()["id"]

    response = client.post(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "manufacturer_id": manufacturer_id,
            "model_code": "ace9000",
            "display_name": "ACE 9000",
            "phase_type": "three_phase",
            "meter_category": "electricity",
            "dlms_capable": True,
            "is_active": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["model_code"] == "ace9000"
    assert db_session.scalar(select(MeterModel).where(MeterModel.model_code == "ace9000")) is not None


def test_create_meter(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    manufacturer_id, meter_model_id = _create_catalog_primitives(client, token)

    response = client.post(
        "/api/v1/meters",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "serial_number": "SN-0001",
            "utility_meter_number": "UMN-0001",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": meter_model_id,
            "current_status": "registered",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["serial_number"] == "SN-0001"
    assert payload["current_status"] == "registered"


def test_duplicate_serial_number_rejected(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    manufacturer_id, meter_model_id = _create_catalog_primitives(client, token)

    meter_payload = {
        "serial_number": "SN-DUPLICATE",
        "utility_meter_number": "UMN-DUPLICATE",
        "manufacturer_id": manufacturer_id,
        "meter_model_id": meter_model_id,
        "current_status": "registered",
    }
    first_response = client.post(
        "/api/v1/meters",
        headers={"Authorization": f"Bearer {token}"},
        json=meter_payload,
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/meters",
        headers={"Authorization": f"Bearer {token}"},
        json={**meter_payload, "utility_meter_number": "UMN-DUPLICATE-2"},
    )

    assert second_response.status_code == 409
    assert "serial number" in second_response.json()["detail"].lower()


def test_meter_status_change_creates_history_row(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    manufacturer_id, meter_model_id = _create_catalog_primitives(client, token)
    meter_id = _create_meter_record(client, token, manufacturer_id, meter_model_id)

    response = client.post(
        f"/api/v1/meters/{meter_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_status": "active", "reason": "Commissioning completed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_status"] == "active"
    assert payload["status_history"][0]["new_status"] == "active"
    assert payload["status_history"][0]["previous_status"] == "registered"

    history_rows = db_session.scalars(
        select(MeterStatusHistory).where(MeterStatusHistory.meter_id == meter_id)
    ).all()
    assert len(history_rows) == 2


def test_meter_write_creates_audit_log(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    manufacturer_id, meter_model_id = _create_catalog_primitives(client, token)

    response = client.post(
        "/api/v1/meters",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "serial_number": "SN-AUDIT-001",
            "utility_meter_number": "UMN-AUDIT-001",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": meter_model_id,
            "current_status": "registered",
        },
    )

    assert response.status_code == 201
    meter = db_session.scalar(select(Meter).where(Meter.serial_number == "SN-AUDIT-001"))
    audit_log = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "meters.create", AuditLog.entity_id == meter.id)
        .order_by(AuditLog.created_at.desc())
    )
    assert audit_log is not None
    assert audit_log.payload["outcome"] == "success"
    assert audit_log.payload["details"]["serial_number"] == "SN-AUDIT-001"


def _create_catalog_primitives(client, token: str) -> tuple[str, str]:
    manufacturer_response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Hexing", "code": "hexing", "country": "China", "is_active": True},
    )
    manufacturer_id = manufacturer_response.json()["id"]

    meter_model_response = client.post(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "manufacturer_id": manufacturer_id,
            "model_code": "hx-300",
            "display_name": "HX-300",
            "phase_type": "single_phase",
            "meter_category": "electricity",
            "dlms_capable": True,
            "is_active": True,
        },
    )
    return manufacturer_id, meter_model_response.json()["id"]


def _create_meter_record(client, token: str, manufacturer_id: str, meter_model_id: str) -> str:
    response = client.post(
        "/api/v1/meters",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "serial_number": "SN-STATUS-001",
            "utility_meter_number": "UMN-STATUS-001",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": meter_model_id,
            "current_status": "registered",
        },
    )
    return response.json()["id"]
