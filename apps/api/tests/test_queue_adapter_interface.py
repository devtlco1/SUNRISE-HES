from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_jobs_scheduler_foundation import _create_job_definition_record, _create_manual_job_run_record
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_retry_dispatch_request_becomes_retry_enqueue_result(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enqueue_result"]["enqueue_category"] == "retry_enqueue_result"
    assert payload["enqueue_result"]["source_job_run_id"] == job_run_id
    assert payload["enqueue_result"]["enqueue_status"] == "accepted"
    assert payload["enqueue_result"]["intended_path"] == "retry_handler_worker_path"


def test_followup_dispatch_request_becomes_followup_enqueue_result(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="followup")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enqueue_result"]["enqueue_category"] == "followup_enqueue_result"
    assert payload["enqueue_result"]["source_job_run_id"] == job_run_id
    assert payload["enqueue_result"]["enqueue_status"] == "accepted"
    assert payload["enqueue_result"]["intended_path"] == "followup_handler_worker_path"


def test_repeated_enqueue_adaptation_calls_stay_idempotent(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    first = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["enqueue_result"] == second.json()["enqueue_result"]


def test_lineage_and_correlation_are_preserved(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    enqueue_result = response.json()["enqueue_result"]
    assert enqueue_result["lineage"]["source_attempt_id"] is not None
    assert enqueue_result["lineage"]["source_command_id"] is not None
    assert enqueue_result["lineage"]["source_job_run_id"] is not None
    assert enqueue_result["derived_correlation_id"] == response.json()["job_run"]["correlation_id"]


def test_non_dispatch_request_input_is_rejected_cleanly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "enqueue-non-dispatch-job")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 409


def test_summaries_remain_consistent_after_enqueue_adaptation(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    assert job_run.result_summary["queue_enqueue"]["enqueue_category"] == "retry_enqueue_result"
    assert job_run.result_summary["queue_enqueue"]["enqueue_status"] == "accepted"
