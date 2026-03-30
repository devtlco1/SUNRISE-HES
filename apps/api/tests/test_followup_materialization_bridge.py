from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_worker_runtime_executor_foundation import _create_started_attempt, _login_as_super_admin


def test_retry_action_materializes_durable_followup_work(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, _, _ = _execute_retryable_attempt(client, db_session, token)

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["materialized_count"] == 1
    item = payload["items"][0]
    assert item["action_type"] == "retry"
    assert item["materialized"] is True

    followup_run = db_session.get(JobRun, item["job_run"]["id"])
    assert followup_run is not None
    assert followup_run.status == "pending"
    assert str(followup_run.related_command_id) == command_id


def test_repeated_materialization_does_not_duplicate_followup_work(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, _ = _execute_retryable_attempt(client, db_session, token)

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["materialized_count"] == 1
    assert second.json()["materialized_count"] == 0
    assert second.json()["existing_count"] == 1
    assert first.json()["items"][0]["job_run"]["id"] == second.json()["items"][0]["job_run"]["id"]


def test_followup_linkage_and_correlation_are_preserved(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, source_job_run_id, _ = _execute_retryable_attempt(client, db_session, token)

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    followup_run = db_session.get(JobRun, response.json()["items"][0]["job_run"]["id"])
    assert followup_run is not None
    assert followup_run.correlation_id == f"followup:{attempt_id}:retry"
    assert followup_run.request_payload["lineage"]["source_attempt_id"] == attempt_id
    assert followup_run.request_payload["lineage"]["source_command_id"] == command_id
    assert followup_run.request_payload["lineage"]["source_job_run_id"] == source_job_run_id
    assert followup_run.request_payload["follow_up"]["action_type"] == "retry"


def test_noop_when_no_followup_actions_exist(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _execute_success_attempt(client, db_session, token)

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["materialized_count"] == 0
    assert response.json()["existing_count"] == 0
    assert response.json()["items"] == []


def test_schedule_followup_action_materializes_work_and_updates_summaries(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _execute_partial_attempt(client, db_session, token)

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["materialized_count"] == 1
    assert payload["items"][0]["action_type"] == "followup_schedule"

    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert attempt.execution_metadata["follow_up_materialization"]["materialized_count"] == 1
    assert command.result_summary["follow_up_materialization"]["materialized_count"] == 1
    assert job_run.result_summary["follow_up_materialization"]["materialized_count"] == 1


def _execute_retryable_attempt(client, db_session: Session, token: str) -> tuple[str, str, str, str]:
    attempt_id, command_id, job_run_id, meter_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "NO_ROUTE",
            "error_message": "Transport unavailable",
        },
        command_template_code="followup-retry-action",
        max_retries=2,
        return_meter_id=True,
    )
    execute = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )
    assert execute.status_code == 200
    return attempt_id, command_id, job_run_id, meter_id


def _execute_success_attempt(client, db_session: Session, token: str) -> tuple[str, str, str]:
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="followup-noop-action",
        max_retries=0,
    )
    execute = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )
    assert execute.status_code == 200
    return attempt_id, command_id, job_run_id


def _execute_partial_attempt(client, db_session: Session, token: str) -> tuple[str, str, str]:
    now = datetime.now(UTC)
    attempt_id, command_id, job_run_id = _create_started_attempt(
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
                        "value_numeric": "10.5",
                        "unit": "kWh",
                        "captured_at": now.isoformat(),
                    }
                ],
            },
        },
        command_template_code="followup-schedule-action",
        max_retries=0,
    )
    execute = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )
    assert execute.status_code == 200
    return attempt_id, command_id, job_run_id
