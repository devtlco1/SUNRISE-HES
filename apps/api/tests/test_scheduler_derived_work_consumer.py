from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_followup_materialization_bridge import (
    _execute_partial_attempt,
    _execute_retryable_attempt,
)
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_retry_derived_job_run_is_classified_and_routed_correctly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, _ = _execute_retryable_attempt(client, db_session, token)
    followup = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    assert followup.status_code == 200
    job_run_id = followup.json()["items"][0]["job_run"]["id"]

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["routing"]["is_derived_work"] is True
    assert payload["routing"]["action_type"] == "retry"
    assert payload["routing"]["routing_category"] == "retry_path"


def test_followup_derived_job_run_is_classified_and_routed_correctly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _execute_partial_attempt(client, db_session, token)
    followup = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    assert followup.status_code == 200
    job_run_id = followup.json()["items"][0]["job_run"]["id"]

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["routing"]["is_derived_work"] is True
    assert payload["routing"]["action_type"] == "followup_schedule"
    assert payload["routing"]["routing_category"] == "followup_path"


def test_repeated_consumption_does_not_duplicate_routing_artifacts(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, _ = _execute_retryable_attempt(client, db_session, token)
    followup = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    job_run_id = followup.json()["items"][0]["job_run"]["id"]

    first = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["routing"]["summary"] == second.json()["routing"]["summary"]


def test_lineage_and_correlation_are_preserved(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, source_job_run_id, _ = _execute_retryable_attempt(client, db_session, token)
    followup = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    job_run_id = followup.json()["items"][0]["job_run"]["id"]

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    routing = response.json()["routing"]
    assert routing["lineage"]["source_attempt_id"] == attempt_id
    assert routing["lineage"]["source_command_id"] == command_id
    assert routing["lineage"]["source_job_run_id"] == source_job_run_id
    assert routing["summary"]["derived_correlation_id"] == f"followup:{attempt_id}:retry"


def test_noop_behavior_when_job_run_is_not_derived_work(client, db_session: Session) -> None:
    from tests.test_jobs_scheduler_foundation import _create_job_definition_record, _create_manual_job_run_record

    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "non-derived-work-job")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["routing"]["is_derived_work"] is False


def test_summaries_remain_consistent_after_routing(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, _ = _execute_retryable_attempt(client, db_session, token)
    followup = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    job_run_id = followup.json()["items"][0]["job_run"]["id"]

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    assert job_run.result_summary["derived_work_routing"]["routing_category"] == "retry_path"
