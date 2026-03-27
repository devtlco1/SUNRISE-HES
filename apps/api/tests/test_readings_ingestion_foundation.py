from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER


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


def test_ingest_reading_batch(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)

    response = client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-reading-batch",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "source_type": "manual_read",
            "captured_at": datetime.now(UTC).isoformat(),
            "status": "received",
            "readings": [
                {
                    "obis_code": "1.0.1.8.0.255",
                    "reading_type": "register",
                    "value_numeric": "123.456",
                    "unit": "kWh",
                    "quality": "good",
                    "captured_at": datetime.now(UTC).isoformat(),
                }
            ],
            "register_snapshots": [
                {
                    "snapshot_type": "billing",
                    "captured_at": datetime.now(UTC).isoformat(),
                    "payload": {"total_import": "123.456"},
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch"]["meter_id"] == meter_id
    assert len(payload["batch"]["readings"]) == 1
    assert len(payload["batch"]["register_snapshots"]) == 1


def test_reject_duplicate_load_profile_interval(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id, channel_id = _create_meter_and_channel(client, token)
    interval_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    interval_end = interval_start + timedelta(minutes=15)

    payload = {
        "source_type": "scheduled_read",
        "captured_at": interval_end.isoformat(),
        "status": "received",
        "load_profile_intervals": [
            {
                "channel_id": channel_id,
                "interval_start": interval_start.isoformat(),
                "interval_end": interval_end.isoformat(),
                "value_numeric": "11.5",
                "quality": "good",
            }
        ],
    }

    first = client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-reading-batch",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json=payload,
    )
    second = client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-reading-batch",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_list_meter_readings(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)

    client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-reading-batch",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "source_type": "manual_read",
            "captured_at": datetime.now(UTC).isoformat(),
            "status": "received",
            "readings": [
                {
                    "obis_code": "1.0.32.7.0.255",
                    "reading_type": "instantaneous",
                    "value_numeric": "230.1",
                    "unit": "V",
                    "quality": "good",
                    "captured_at": datetime.now(UTC).isoformat(),
                }
            ],
        },
    )

    response = client.get(
        f"/api/v1/meters/{meter_id}/readings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["obis_code"] == "1.0.32.7.0.255"


def test_ingest_meter_events(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)

    response = client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-events",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "correlation_id": "evt-1",
            "events": [
                {
                    "event_code": "power_failure",
                    "event_name": "Power Failure",
                    "severity": "critical",
                    "event_state": "open",
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "raw_payload": {"raw": "payload"},
                    "normalized_payload": {"reason": "power_loss"},
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["total_ingested"] == 1


def test_admin_create_update_load_profile_channel(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)

    create_response = client.post(
        f"/api/v1/meters/{meter_id}/load-profile-channels",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel_code": "lp-a",
            "obis_code": "1.0.99.1.0.255",
            "unit": "kWh",
            "interval_seconds": 900,
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    channel_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/load-profile-channels/{channel_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"unit": "Wh", "is_active": False},
    )

    assert update_response.status_code == 200
    assert update_response.json()["unit"] == "Wh"
    assert update_response.json()["is_active"] is False


def _create_meter_record(client, token: str) -> str:
    suffix = str(int(datetime.now(UTC).timestamp() * 1000))
    manufacturer_response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Readings Vendor {suffix}",
            "code": f"readings-vendor-{suffix}",
            "country": "Oman",
            "is_active": True,
        },
    )
    assert manufacturer_response.status_code == 201
    manufacturer_id = manufacturer_response.json()["id"]

    model_response = client.post(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "manufacturer_id": manufacturer_id,
            "model_code": f"readings-model-{suffix}",
            "display_name": "Readings Model",
            "phase_type": "single_phase",
            "meter_category": "electricity",
            "dlms_capable": True,
            "is_active": True,
        },
    )
    assert model_response.status_code == 201

    meter_response = client.post(
        "/api/v1/meters",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "serial_number": f"READINGS-METER-{suffix}",
            "utility_meter_number": f"READINGS-UMN-{suffix}",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": model_response.json()["id"],
            "current_status": "registered",
        },
    )
    assert meter_response.status_code == 201
    return meter_response.json()["id"]


def _create_meter_and_channel(client, token: str) -> tuple[str, str]:
    meter_id = _create_meter_record(client, token)
    channel_response = client.post(
        f"/api/v1/meters/{meter_id}/load-profile-channels",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel_code": "lp-main",
            "obis_code": "1.0.99.1.0.255",
            "unit": "kWh",
            "interval_seconds": 900,
            "is_active": True,
        },
    )
    assert channel_response.status_code == 201
    return meter_id, channel_response.json()["id"]
