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


def test_assign_meter_target_to_job_definition(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id, meter_id = _create_interval_job_definition_with_meter(client, token)

    response = client.post(
        f"/api/v1/job-definitions/{job_definition_id}/targets",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_meter_id": meter_id, "notes": "Primary schedule target"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["target_meter_id"] == meter_id


def test_generate_due_job_runs_from_interval_definition(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id, meter_id = _create_interval_job_definition_with_meter(client, token)
    _assign_target(client, token, job_definition_id, meter_id)

    response = client.post(
        "/api/v1/internal/scheduler/generate-due-runs",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "as_of": datetime.now(UTC).isoformat(),
            "window_seconds": 300,
            "job_definition_id": job_definition_id,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] >= 1
    assert payload["items"][0]["target_meter_id"] == meter_id


def test_repeated_generation_returns_no_duplicates(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id, meter_id = _create_interval_job_definition_with_meter(client, token)
    _assign_target(client, token, job_definition_id, meter_id)
    request_payload = {
        "as_of": datetime.now(UTC).isoformat(),
        "window_seconds": 300,
        "job_definition_id": job_definition_id,
    }

    first = client.post(
        "/api/v1/internal/scheduler/generate-due-runs",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json=request_payload,
    )
    second = client.post(
        "/api/v1/internal/scheduler/generate-due-runs",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json=request_payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created_count"] >= 1
    assert second.json()["created_count"] == 0
    assert second.json()["skipped_existing_count"] >= 1


def test_once_schedule_does_not_duplicate_on_repeated_calls(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id, meter_id = _create_once_job_definition_with_meter(client, token)
    _assign_target(client, token, job_definition_id, meter_id)
    request_payload = {
        "as_of": datetime.now(UTC).isoformat(),
        "window_seconds": 3600,
        "job_definition_id": job_definition_id,
    }

    first = client.post(
        "/api/v1/internal/scheduler/generate-due-runs",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json=request_payload,
    )
    second = client.post(
        "/api/v1/internal/scheduler/generate-due-runs",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json=request_payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created_count"] == 1
    assert second.json()["created_count"] == 0


def test_manual_definition_does_not_auto_generate(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id, meter_id = _create_manual_job_definition_with_meter(client, token)
    _assign_target(client, token, job_definition_id, meter_id)

    response = client.post(
        "/api/v1/internal/scheduler/generate-due-runs",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "as_of": datetime.now(UTC).isoformat(),
            "window_seconds": 600,
            "job_definition_id": job_definition_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 0


def test_target_list_shows_assignments(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id, meter_id = _create_interval_job_definition_with_meter(client, token)
    _assign_target(client, token, job_definition_id, meter_id)

    response = client.get(
        f"/api/v1/job-definitions/{job_definition_id}/targets",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["target_meter_id"] == meter_id


def _assign_target(client, token: str, job_definition_id: str, meter_id: str) -> None:
    response = client.post(
        f"/api/v1/job-definitions/{job_definition_id}/targets",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_meter_id": meter_id},
    )
    assert response.status_code == 201


def _create_interval_job_definition_with_meter(client, token: str) -> tuple[str, str]:
    from tests.test_jobs_scheduler_foundation import _create_command_template_record, _create_meter_record

    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(
        client,
        token,
        f"interval-template-{int(datetime.now(UTC).timestamp() * 1000)}",
    )
    response = client.post(
        "/api/v1/job-definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": f"interval-job-{int(datetime.now(UTC).timestamp() * 1000)}",
            "name": "Interval Job",
            "category": "command",
            "target_type": "meter",
            "schedule_type": "interval",
            "interval_seconds": 60,
            "run_at": (datetime.now(UTC) - timedelta(seconds=60)).isoformat(),
            "command_template_id": template_id,
            "priority": "normal",
            "timeout_seconds": 120,
            "max_retries": 1,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"], meter_id


def _create_once_job_definition_with_meter(client, token: str) -> tuple[str, str]:
    from tests.test_jobs_scheduler_foundation import _create_command_template_record, _create_meter_record

    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(
        client,
        token,
        f"once-template-{int(datetime.now(UTC).timestamp() * 1000)}",
    )
    response = client.post(
        "/api/v1/job-definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": f"once-job-{int(datetime.now(UTC).timestamp() * 1000)}",
            "name": "Once Job",
            "category": "command",
            "target_type": "meter",
            "schedule_type": "once",
            "run_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
            "command_template_id": template_id,
            "priority": "normal",
            "timeout_seconds": 120,
            "max_retries": 1,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"], meter_id


def _create_manual_job_definition_with_meter(client, token: str) -> tuple[str, str]:
    from tests.test_jobs_scheduler_foundation import _create_command_template_record, _create_meter_record

    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(
        client,
        token,
        f"manual-template-{int(datetime.now(UTC).timestamp() * 1000)}",
    )
    response = client.post(
        "/api/v1/job-definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": f"manual-job-{int(datetime.now(UTC).timestamp() * 1000)}",
            "name": "Manual Job",
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
    return response.json()["id"], meter_id
