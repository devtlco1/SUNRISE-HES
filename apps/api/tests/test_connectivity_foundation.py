from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.connectivity.enums import ConnectivitySessionPurpose, ConnectivitySessionStatus
from app.modules.connectivity.models import (
    CommunicationEndpoint,
    ConnectivitySessionHistory,
    MeterEndpointAssignment,
    ProtocolAssociationProfile,
)


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


def test_create_communication_endpoint(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.post(
        "/api/v1/communication-endpoints",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "tcp-endpoint-1",
            "display_name": "Primary TCP Endpoint",
            "endpoint_type": "tcp",
            "transport_type": "tcp_ip",
            "host": "10.10.10.10",
            "port": 4059,
            "ip_address": "10.10.10.10",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["code"] == "tcp-endpoint-1"
    assert db_session.scalar(
        select(CommunicationEndpoint).where(CommunicationEndpoint.code == "tcp-endpoint-1")
    ) is not None


def test_create_protocol_association_profile(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.post(
        "/api/v1/protocol-association-profiles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "dlms-default",
            "name": "DLMS Default",
            "protocol_family": "dlms_cosem",
            "iec62056_21_enabled": True,
            "client_address": 16,
            "server_address": 1,
            "authentication_mode": "low",
            "password_secret_ref": "vault://dlms/default-password",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["code"] == "dlms-default"
    assert db_session.scalar(
        select(ProtocolAssociationProfile).where(ProtocolAssociationProfile.code == "dlms-default")
    ) is not None


def test_assign_endpoint_to_meter(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_id = _create_endpoint_record(client, token, "assign-endpoint-1")

    response = client.post(
        f"/api/v1/meters/{meter_id}/endpoint-assignments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "endpoint_id": endpoint_id,
            "is_primary": True,
            "assignment_status": "active",
            "notes": "Primary connectivity path",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["is_primary"] is True
    assert payload["assignment_status"] == "active"


def test_prevent_second_active_primary_assignment(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_one = _create_endpoint_record(client, token, "assign-endpoint-primary-1")
    endpoint_two = _create_endpoint_record(client, token, "assign-endpoint-primary-2")

    first_response = client.post(
        f"/api/v1/meters/{meter_id}/endpoint-assignments",
        headers={"Authorization": f"Bearer {token}"},
        json={"endpoint_id": endpoint_one, "is_primary": True, "assignment_status": "active"},
    )
    assert first_response.status_code == 201

    second_response = client.post(
        f"/api/v1/meters/{meter_id}/endpoint-assignments",
        headers={"Authorization": f"Bearer {token}"},
        json={"endpoint_id": endpoint_two, "is_primary": True, "assignment_status": "active"},
    )

    assert second_response.status_code == 409
    assert "active primary" in second_response.json()["detail"].lower()


def test_list_meter_session_history(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_id = _create_endpoint_record(client, token, "session-endpoint-1")

    session_history = ConnectivitySessionHistory(
        meter_id=meter_id,
        endpoint_id=endpoint_id,
        status=ConnectivitySessionStatus.SUCCEEDED,
        session_purpose=ConnectivitySessionPurpose.CONNECTIVITY_TEST,
        correlation_id="session-corr-1",
        bytes_sent=120,
        bytes_received=350,
    )
    db_session.add(session_history)
    db_session.commit()

    response = client.get(
        f"/api/v1/meters/{meter_id}/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["correlation_id"] == "session-corr-1"


def test_connectivity_write_creates_audit_log(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.post(
        "/api/v1/communication-endpoints",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "audit-endpoint-1",
            "display_name": "Audit Endpoint",
            "endpoint_type": "tcp",
            "transport_type": "tcp_ip",
            "host": "10.10.20.20",
            "port": 4060,
            "is_active": True,
        },
    )

    assert response.status_code == 201
    endpoint = db_session.scalar(
        select(CommunicationEndpoint).where(CommunicationEndpoint.code == "audit-endpoint-1")
    )
    audit_log = db_session.scalar(
        select(AuditLog)
        .where(
            AuditLog.action == "connectivity.endpoints.create",
            AuditLog.entity_id == endpoint.id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    assert audit_log is not None
    assert audit_log.payload["outcome"] == "success"
    assert audit_log.payload["details"]["code"] == "audit-endpoint-1"


def _create_endpoint_record(client, token: str, code: str) -> str:
    response = client.post(
        "/api/v1/communication-endpoints",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "display_name": f"Endpoint {code}",
            "endpoint_type": "tcp",
            "transport_type": "tcp_ip",
            "host": "10.0.0.1",
            "port": 4059,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_meter_record(client, token: str) -> str:
    manufacturer_response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Connectivity Vendor", "code": "connectivity-vendor", "country": "Oman", "is_active": True},
    )
    assert manufacturer_response.status_code == 201
    manufacturer_id = manufacturer_response.json()["id"]

    model_response = client.post(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "manufacturer_id": manufacturer_id,
            "model_code": "connectivity-model",
            "display_name": "Connectivity Model",
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
            "serial_number": "CONNECTIVITY-METER-1",
            "utility_meter_number": "CONNECTIVITY-UMN-1",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": model_response.json()["id"],
            "current_status": "registered",
        },
    )
    assert meter_response.status_code == 201
    return meter_response.json()["id"]
