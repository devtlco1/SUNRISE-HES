from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_followup_materialization_bridge import (
    _execute_partial_attempt,
    _execute_retryable_attempt,
)
from tests.test_jobs_scheduler_foundation import _create_job_definition_record, _create_manual_job_run_record
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_retry_path_runs_are_exposed_through_retry_pickup(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="retry")

    response = client.get(
        "/api/v1/internal/job-runs/derived-work-pickup",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"pickup_category": "retry_pickup"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["retry_items"][0]["job_run"]["id"] == job_run_id
    assert payload["retry_items"][0]["pickup_category"] == "retry_pickup"
    assert payload["retry_items"][0]["routing_category"] == "retry_path"
    assert payload["followup_items"] == []


def test_followup_path_runs_are_exposed_through_followup_pickup(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="followup")

    response = client.get(
        "/api/v1/internal/job-runs/derived-work-pickup",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"pickup_category": "followup_pickup"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["followup_items"][0]["job_run"]["id"] == job_run_id
    assert payload["followup_items"][0]["pickup_category"] == "followup_pickup"
    assert payload["followup_items"][0]["routing_category"] == "followup_path"
    assert payload["retry_items"] == []


def test_repeated_pickup_calls_stay_idempotent(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    _prepare_routed_derived_job_run(client, db_session, token, mode="retry")

    first = client.get(
        "/api/v1/internal/job-runs/derived-work-pickup",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.get(
        "/api/v1/internal/job-runs/derived-work-pickup",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_lineage_and_correlation_are_preserved_in_pickup_output(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, source_job_run_id, _ = _execute_retryable_attempt(client, db_session, token)
    materialize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    derived_job_run_id = materialize.json()["items"][0]["job_run"]["id"]
    consume = client.post(
        f"/api/v1/internal/job-runs/{derived_job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    assert consume.status_code == 200

    response = client.get(
        "/api/v1/internal/job-runs/derived-work-pickup",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"pickup_category": "retry_pickup"},
    )

    assert response.status_code == 200
    item = response.json()["retry_items"][0]
    assert item["lineage"]["source_attempt_id"] == attempt_id
    assert item["lineage"]["source_command_id"] == command_id
    assert item["lineage"]["source_job_run_id"] == source_job_run_id
    assert item["job_run"]["correlation_id"] == f"followup:{attempt_id}:retry"


def test_non_derived_runs_are_excluded_cleanly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "pickup-non-derived-work-job")
    _create_manual_job_run_record(client, token, job_definition_id)

    response = client.get(
        "/api/v1/internal/job-runs/derived-work-pickup",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["retry_items"] == []
    assert response.json()["followup_items"] == []


def test_projections_remain_consistent_without_mutating_summaries(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="retry")
    before = db_session.get(JobRun, job_run_id)
    assert before is not None
    before_summary = before.result_summary

    response = client.get(
        "/api/v1/internal/job-runs/derived-work-pickup",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    after = db_session.get(JobRun, job_run_id)
    assert after is not None
    assert after.result_summary == before_summary


def _prepare_routed_derived_job_run(client, db_session: Session, token: str, *, mode: str) -> str:
    if mode == "retry":
        attempt_id, _, _, _ = _execute_retryable_attempt(client, db_session, token)
    else:
        attempt_id, _, _ = _execute_partial_attempt(client, db_session, token)

    materialize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/materialize-follow-up-actions",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    assert materialize.status_code == 200
    job_run_id = materialize.json()["items"][0]["job_run"]["id"]

    consume = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/consume-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    assert consume.status_code == 200
    return job_run_id
