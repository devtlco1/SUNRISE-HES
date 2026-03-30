from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_jobs_scheduler_foundation import _create_job_definition_record, _create_manual_job_run_record
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_retry_dispatch_ready_work_becomes_retry_dispatch_request(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-requests",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"dispatch_category": "retry_dispatch_request"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["retry_items"][0]
    assert item["job_run"]["id"] == job_run_id
    assert item["dispatch_category"] == "retry_dispatch_request"
    assert item["intended_path"] == "retry_handler_worker_path"
    assert payload["followup_items"] == []


def test_followup_dispatch_ready_work_becomes_followup_dispatch_request(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="followup")

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-requests",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"dispatch_category": "followup_dispatch_request"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["followup_items"][0]
    assert item["job_run"]["id"] == job_run_id
    assert item["dispatch_category"] == "followup_dispatch_request"
    assert item["intended_path"] == "followup_handler_worker_path"
    assert payload["retry_items"] == []


def test_repeated_adaptation_calls_stay_idempotent(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    first = client.get(
        "/api/v1/internal/job-runs/dispatch-requests",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.get(
        "/api/v1/internal/job-runs/dispatch-requests",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_lineage_and_correlation_are_preserved(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-requests",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"dispatch_category": "retry_dispatch_request"},
    )

    assert response.status_code == 200
    item = response.json()["retry_items"][0]
    assert item["job_run"]["id"] == job_run_id
    assert item["lineage"]["source_attempt_id"] is not None
    assert item["lineage"]["source_command_id"] is not None
    assert item["lineage"]["source_job_run_id"] is not None
    assert item["derived_correlation_id"] == item["job_run"]["correlation_id"]


def test_non_dispatch_ready_inputs_are_excluded_cleanly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "dispatch-adapter-non-ready-job")
    _create_manual_job_run_record(client, token, job_definition_id)

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-requests",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["retry_items"] == []
    assert response.json()["followup_items"] == []


def test_summaries_remain_consistent_after_adaptation(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")
    before = db_session.get(JobRun, job_run_id)
    assert before is not None
    before_summary = before.result_summary

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-requests",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    after = db_session.get(JobRun, job_run_id)
    assert after is not None
    assert after.result_summary == before_summary
