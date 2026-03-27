from datetime import UTC, datetime

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


def test_materialize_command_from_eligible_job_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_job_run_ready_for_materialization(client, token)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/materialize-command",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["materialized"] is True
    assert payload["command"]["meter_id"] == payload["job_run"]["target_meter_id"]
    assert payload["job_run"]["related_command"]["id"] == payload["command"]["id"]


def test_repeated_materialization_returns_same_meter_command(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_job_run_ready_for_materialization(client, token)

    first = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/materialize-command",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/materialize-command",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["command"]["id"] == second.json()["command"]["id"]
    assert second.json()["materialized"] is False


def test_reject_materialization_for_non_eligible_job_run(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_job_run_ready_for_materialization(client, token)

    from app.modules.jobs.models import JobRun

    job_run = db_session.get(JobRun, job_run_id)
    job_run.status = "succeeded"
    db_session.add(job_run)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/materialize-command",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 409
    assert "cannot be materialized" in response.json()["detail"].lower()


def test_job_run_detail_shows_related_meter_command(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _create_job_run_ready_for_materialization(client, token)

    materialized = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/materialize-command",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    assert materialized.status_code == 200

    detail = client.get(
        f"/api/v1/job-runs/{job_run_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["related_command"]["id"] == materialized.json()["command"]["id"]
    assert payload["related_command"]["current_status"] == materialized.json()["command"]["current_status"]


def _create_job_run_ready_for_materialization(client, token: str) -> str:
    from tests.test_jobs_scheduler_foundation import (
        _create_command_template_record,
        _create_job_definition_record,
        _create_manual_job_run_record,
        _create_meter_record,
    )

    meter_id = _create_meter_record(client, token)
    command_template_id = _create_command_template_record(
        client,
        token,
        f"materialize-template-{int(datetime.now(UTC).timestamp() * 1000)}",
    )
    job_definition_id = _create_job_definition_record(
        client,
        token,
        f"materialize-job-{int(datetime.now(UTC).timestamp() * 1000)}",
    )

    response = client.patch(
        f"/api/v1/job-definitions/{job_definition_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"command_template_id": command_template_id},
    )
    assert response.status_code == 200

    response = client.post(
        f"/api/v1/job-definitions/{job_definition_id}/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_meter_id": meter_id,
            "scheduled_for": datetime.now(UTC).isoformat(),
            "available_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]
