from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, CommandTemplate, MeterCommand


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


def test_create_command_template(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)

    response = client.post(
        "/api/v1/command-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "remote-disconnect",
            "name": "Remote Disconnect",
            "category": "remote_disconnect",
            "description": "Disconnect service remotely",
            "target_scope": "meter",
            "payload_schema": {"type": "object"},
            "timeout_seconds": 180,
            "max_retries": 2,
            "is_active": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["code"] == "remote-disconnect"
    assert db_session.scalar(
        select(CommandTemplate).where(CommandTemplate.code == "remote-disconnect")
    ) is not None


def test_create_command_request_for_meter(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "on-demand-read")

    response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "priority": "high",
            "request_payload": {"obis": "1.0.1.8.0.255"},
            "idempotency_key": "cmd-idem-1",
            "notes": "Manual read request",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["current_status"] == "pending"
    assert payload["priority"] == "high"


def test_duplicate_idempotency_handling(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "clock-sync")

    first_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "idempotency_key": "cmd-idem-duplicate",
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "idempotency_key": "cmd-idem-duplicate",
        },
    )

    assert second_response.status_code == 409
    assert "idempotency key" in second_response.json()["detail"].lower()


def test_list_meter_command_history(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "connectivity-test")

    create_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"command_template_id": template_id},
    )
    assert create_response.status_code == 201

    list_response = client.get(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["command_template_code"] == "connectivity-test"


def test_command_attempt_history_read(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "profile-capture")

    create_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"command_template_id": template_id},
    )
    command_id = create_response.json()["id"]

    db_session.add(
        CommandExecutionAttempt(
            meter_command_id=command_id,
            attempt_number=1,
            status=CommandExecutionAttemptStatus.FAILED,
            error_code="NO_ROUTE",
            error_message="No route to device",
        )
    )
    db_session.commit()

    attempts_response = client.get(
        f"/api/v1/commands/{command_id}/attempts",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert attempts_response.status_code == 200
    payload = attempts_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["error_code"] == "NO_ROUTE"


def test_command_write_creates_audit_log(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "remote-reconnect")

    response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "priority": "urgent",
            "idempotency_key": "audit-command-1",
        },
    )

    assert response.status_code == 201
    command = db_session.scalar(
        select(MeterCommand).where(MeterCommand.idempotency_key == "audit-command-1")
    )
    audit_log = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "commands.requests.create", AuditLog.entity_id == command.id)
        .order_by(AuditLog.created_at.desc())
    )
    assert audit_log is not None
    assert audit_log.payload["outcome"] == "success"
    assert audit_log.payload["details"]["template_code"] == "remote-reconnect"


def _create_command_template_record(client, token: str, code: str) -> str:
    response = client.post(
        "/api/v1/command-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "name": code.replace("-", " ").title(),
            "category": "on_demand_read",
            "target_scope": "meter",
            "timeout_seconds": 120,
            "max_retries": 1,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_meter_record(client, token: str) -> str:
    manufacturer_response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Command Vendor", "code": "command-vendor", "country": "Oman", "is_active": True},
    )
    assert manufacturer_response.status_code == 201
    manufacturer_id = manufacturer_response.json()["id"]

    model_response = client.post(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "manufacturer_id": manufacturer_id,
            "model_code": "command-model",
            "display_name": "Command Model",
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
            "serial_number": "COMMAND-METER-1",
            "utility_meter_number": "COMMAND-UMN-1",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": model_response.json()["id"],
            "current_status": "registered",
        },
    )
    assert meter_response.status_code == 201
    return meter_response.json()["id"]
