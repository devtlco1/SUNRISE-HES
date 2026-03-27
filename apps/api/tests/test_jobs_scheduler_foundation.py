from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.commands.models import CommandTemplate, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobDefinition, JobRun


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


def test_create_job_definition(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    template_id = _create_command_template_record(client, token, "scheduled-meter-read")

    response = client.post(
        "/api/v1/job-definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "daily-meter-read",
            "name": "Daily Meter Read",
            "category": "meter_read",
            "target_type": "meter",
            "schedule_type": "cron",
            "cron_expression": "0 0 * * *",
            "command_template_id": template_id,
            "priority": "normal",
            "timeout_seconds": 300,
            "max_retries": 2,
            "is_active": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["code"] == "daily-meter-read"
    assert db_session.scalar(select(JobDefinition).where(JobDefinition.code == "daily-meter-read")) is not None


def test_claim_eligible_job_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "claim-job")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    response = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-a", "limit": 5, "lease_seconds": 60},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["claimed_count"] == 1
    assert payload["items"][0]["id"] == job_run_id
    assert payload["items"][0]["status"] == "claimed"


def test_reject_already_claimed_or_non_eligible_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "already-claimed-job")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    first_claim = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-a", "limit": 5, "lease_seconds": 60},
    )
    assert first_claim.status_code == 200

    second_claim = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-b", "limit": 5, "lease_seconds": 60},
    )

    assert second_claim.status_code == 200
    assert second_claim.json()["claimed_count"] == 0

    job_run = db_session.get(JobRun, job_run_id)
    assert job_run.status == JobRunStatus.CLAIMED


def test_valid_command_cancel_from_pending(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "cancel-command")
    command_id = _create_command_record(client, token, meter_id, template_id, "cancel-key-1")

    response = client.post(
        f"/api/v1/commands/{command_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "No longer needed"},
    )

    assert response.status_code == 200
    assert response.json()["current_status"] == "cancelled"


def test_reject_cancel_from_completed_state(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "completed-command")
    command_id = _create_command_record(client, token, meter_id, template_id, "cancel-key-2")

    command = db_session.get(MeterCommand, command_id)
    command.current_status = "succeeded"
    db_session.add(command)
    db_session.commit()

    response = client.post(
        f"/api/v1/commands/{command_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Should fail"},
    )

    assert response.status_code == 409
    assert "cannot be cancelled" in response.json()["detail"].lower()


def test_audited_write_action_exists_for_job_definition(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    template_id = _create_command_template_record(client, token, "audit-job-template")

    response = client.post(
        "/api/v1/job-definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "audit-job",
            "name": "Audit Job",
            "category": "command",
            "target_type": "meter",
            "schedule_type": "manual",
            "command_template_id": template_id,
            "priority": "high",
            "timeout_seconds": 180,
            "max_retries": 1,
            "is_active": True,
        },
    )

    assert response.status_code == 201
    job_definition = db_session.scalar(select(JobDefinition).where(JobDefinition.code == "audit-job"))
    audit_log = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "jobs.definitions.create", AuditLog.entity_id == job_definition.id)
        .order_by(AuditLog.created_at.desc())
    )
    assert audit_log is not None
    assert audit_log.payload["outcome"] == "success"


def _create_job_definition_record(client, token: str, code: str) -> str:
    template_id = _create_command_template_record(client, token, f"{code}-template")
    response = client.post(
        "/api/v1/job-definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "name": code.replace("-", " ").title(),
            "category": "command",
            "target_type": "meter",
            "schedule_type": "manual",
            "command_template_id": template_id,
            "priority": "normal",
            "timeout_seconds": 120,
            "max_retries": 1,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_manual_job_run_record(client, token: str, job_definition_id: str) -> str:
    response = client.post(
        f"/api/v1/job-definitions/{job_definition_id}/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "scheduled_for": datetime.now(UTC).isoformat(),
            "available_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


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
    suffix = str(int(datetime.now(UTC).timestamp() * 1000))
    manufacturer_response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Job Vendor {suffix}",
            "code": f"job-vendor-{suffix}",
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
            "model_code": f"job-model-{suffix}",
            "display_name": "Job Model",
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
            "serial_number": f"JOB-METER-{suffix}",
            "utility_meter_number": f"JOB-UMN-{suffix}",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": model_response.json()["id"],
            "current_status": "registered",
        },
    )
    assert meter_response.status_code == 201
    return meter_response.json()["id"]


def _create_command_record(client, token: str, meter_id: str, template_id: str, idempotency_key: str) -> str:
    response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "idempotency_key": idempotency_key,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]
