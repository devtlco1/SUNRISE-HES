from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.events.models import MeterEventIngestion
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.modules.commands.models import MeterCommand
from app.modules.connectivity.models import ConnectivitySessionHistory
from tests.test_worker_runtime_executor_foundation import _create_started_attempt, _login_as_super_admin


def test_followup_signal_consumption(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    now = datetime.now(UTC)
    attempt_id, _, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "partial",
            "reading_batch": {
                "source_type": "command_result",
                "captured_at": now.isoformat(),
                "status": "received",
                "readings": [
                    {
                        "obis_code": "1.0.1.8.0.255",
                        "reading_type": "register",
                        "value_numeric": "5.0",
                        "unit": "kWh",
                        "captured_at": now.isoformat(),
                    }
                ],
            },
        },
        command_template_code="runtime-downstream-followup",
        max_retries=1,
        return_meter_id=True,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["downstream_consumption"]["follow_up_actions"][0]["action_type"] == "followup_schedule"


def test_operational_event_signal_consumption(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "AUTH_FAILED",
            "error_message": "Association rejected",
        },
        command_template_code="runtime-downstream-event",
        max_retries=1,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["downstream_consumption"]["operational_event_created"] is True
    event = db_session.query(MeterEventIngestion).filter(
        MeterEventIngestion.related_attempt_id == attempt_id,
        MeterEventIngestion.event_code == "runtime_signal.permanent_failure",
    ).one()
    assert event.normalized_payload["outcome_category"] == "permanent_failure"


def test_endpoint_unhealthy_signal_consumption(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "NO_ROUTE",
            "error_message": "Transport unavailable",
        },
        command_template_code="runtime-downstream-endpoint-health",
        max_retries=1,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["downstream_consumption"]["endpoint_health_hint"]["status"] == "degraded"
    session_history = db_session.get(ConnectivitySessionHistory, payload["session"]["id"])
    assert session_history is not None
    assert session_history.metadata_json["endpoint_health_hint"]["status"] == "degraded"


def test_noop_behavior_when_no_signals_require_action(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-downstream-noop",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["downstream_consumption"]["follow_up_actions"] == []
    assert payload["downstream_consumption"]["operational_event_created"] is False
    assert payload["downstream_consumption"]["endpoint_health_hint"] is None


def test_summary_consistency_after_signal_consumption(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "NO_ROUTE",
            "error_message": "Transport unavailable",
        },
        command_template_code="runtime-downstream-summary",
        max_retries=1,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert command is not None
    assert job_run is not None
    assert command.result_summary["downstream_signal_consumption"]["summary"]["follow_up_action_count"] == 1
    assert job_run.result_summary["downstream_signal_consumption"]["summary"]["follow_up_action_count"] == 1
