from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_jobs_scheduler_foundation import _create_job_definition_record, _create_manual_job_run_record
from tests.test_scheduler_pickup_policy_foundation import _prepare_routed_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_retry_handler_work_is_coordinated_into_retry_dispatch_ready(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-ready-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"coordination_category": "retry_dispatch_ready"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["retry_items"][0]["job_run"]["id"] == job_run_id
    assert payload["retry_items"][0]["coordination_category"] == "retry_dispatch_ready"
    assert payload["retry_items"][0]["handler_category"] == "retry_handler"
    assert payload["followup_items"] == []


def test_followup_handler_work_is_coordinated_into_followup_dispatch_ready(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="followup")

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-ready-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"coordination_category": "followup_dispatch_ready"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["followup_items"][0]["job_run"]["id"] == job_run_id
    assert payload["followup_items"][0]["coordination_category"] == "followup_dispatch_ready"
    assert payload["followup_items"][0]["handler_category"] == "followup_handler"
    assert payload["retry_items"] == []


def test_repeated_coordination_calls_stay_idempotent(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    first = client.get(
        "/api/v1/internal/job-runs/dispatch-ready-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.get(
        "/api/v1/internal/job-runs/dispatch-ready-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_lineage_and_correlation_are_preserved(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-ready-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        params={"coordination_category": "retry_dispatch_ready"},
    )

    assert response.status_code == 200
    item = response.json()["retry_items"][0]
    assert item["job_run"]["id"] == job_run_id
    assert item["lineage"]["source_attempt_id"] is not None
    assert item["lineage"]["source_command_id"] is not None
    assert item["lineage"]["source_job_run_id"] is not None
    assert item["job_run"]["correlation_id"] is not None


def test_non_handled_inputs_are_excluded_cleanly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "coordinator-non-handled-job")
    _create_manual_job_run_record(client, token, job_definition_id)

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-ready-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["retry_items"] == []
    assert response.json()["followup_items"] == []


def test_summaries_remain_consistent_after_coordination(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")
    before = db_session.get(JobRun, job_run_id)
    assert before is not None
    before_summary = before.result_summary

    response = client.get(
        "/api/v1/internal/job-runs/dispatch-ready-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    after = db_session.get(JobRun, job_run_id)
    assert after is not None
    assert after.result_summary == before_summary


def _prepare_handled_derived_job_run(client, db_session: Session, token: str, *, mode: str) -> str:
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode=mode)
    handle = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    assert handle.status_code == 200
    return job_run_id
