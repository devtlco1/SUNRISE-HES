from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_protocol_runtime_foundation import _create_meter_record


def test_recent_events_returns_compact_global_event_list_ordered_by_occurred_at(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    now = datetime.now(UTC)

    ingest_response = client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-events",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "correlation_id": "recent-events-1",
            "events": [
                {
                    "event_code": "power_restore",
                    "event_name": "Power Restore",
                    "severity": "info",
                    "event_state": "resolved",
                    "occurred_at": (now - timedelta(minutes=10)).isoformat(),
                    "normalized_payload": {"source": "test"},
                },
                {
                    "event_code": "tamper_open",
                    "event_name": "Tamper Open",
                    "severity": "critical",
                    "event_state": "open",
                    "occurred_at": now.isoformat(),
                    "normalized_payload": {"source": "test"},
                },
            ],
        },
    )
    assert ingest_response.status_code == 200

    response = client.get(
        "/api/v1/events/recent?limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 2
    assert payload["items"][0]["event_code"] == "tamper_open"
    assert payload["items"][0]["severity"] == "critical"
    assert payload["items"][0]["event_state"] == "open"
    assert payload["items"][0]["meter_id"] == meter_id
    assert payload["items"][1]["event_code"] == "power_restore"


def test_recent_events_respects_limit_for_compact_global_event_list(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    now = datetime.now(UTC)

    ingest_response = client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-events",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "correlation_id": "recent-events-limit-1",
            "events": [
                {
                    "event_code": "voltage_sag",
                    "event_name": "Voltage Sag",
                    "severity": "warning",
                    "event_state": "open",
                    "occurred_at": (now - timedelta(minutes=5)).isoformat(),
                },
                {
                    "event_code": "cover_open",
                    "event_name": "Cover Open",
                    "severity": "critical",
                    "event_state": "open",
                    "occurred_at": now.isoformat(),
                },
            ],
        },
    )
    assert ingest_response.status_code == 200

    response = client.get(
        "/api/v1/events/recent?limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_event_detail_returns_bounded_operational_event_payload(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    now = datetime.now(UTC)

    ingest_response = client.post(
        f"/api/v1/internal/meters/{meter_id}/ingest-events",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "correlation_id": "event-detail-1",
            "events": [
                {
                    "event_code": "cover_open",
                    "event_name": "Cover Open",
                    "severity": "critical",
                    "event_state": "open",
                    "occurred_at": now.isoformat(),
                    "normalized_payload": {"origin": "detail-test"},
                }
            ],
        },
    )
    assert ingest_response.status_code == 200
    event_id = ingest_response.json()["items"][0]["id"]

    response = client.get(
        f"/api/v1/events/{event_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == event_id
    assert payload["meter_id"] == meter_id
    assert payload["event_code"] == "cover_open"
    assert payload["event_state"] == "open"
    assert payload["severity"] == "critical"


def test_event_detail_returns_not_found_for_unknown_event(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.get(
        "/api/v1/events/00000000-0000-0000-0000-000000000001",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Operational event not found."
