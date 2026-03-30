from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_jobs_scheduler_foundation import _create_job_definition_record, _create_manual_job_run_record
from tests.test_scheduler_pickup_policy_foundation import _prepare_routed_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_retry_pickup_is_handled_through_retry_handler_correctly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["handler"]["handled"] is True
    assert payload["handler"]["handler_category"] == "retry_handler"
    assert payload["handler"]["pickup_category"] == "retry_pickup"
    assert payload["handler"]["should_remain_pending"] is True


def test_followup_pickup_is_handled_through_followup_handler_correctly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="followup")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["handler"]["handled"] is True
    assert payload["handler"]["handler_category"] == "followup_handler"
    assert payload["handler"]["pickup_category"] == "followup_pickup"
    assert payload["handler"]["should_remain_pending"] is True


def test_repeated_handling_calls_stay_idempotent(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="retry")

    first = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["handler"] == second.json()["handler"]


def test_lineage_and_correlation_are_preserved(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["handler"]["lineage"]["source_attempt_id"] is not None
    assert payload["handler"]["lineage"]["source_command_id"] is not None
    assert payload["handler"]["lineage"]["source_job_run_id"] is not None
    assert payload["handler"]["summary"]["derived_correlation_id"] == payload["job_run"]["correlation_id"]


def test_non_derived_input_is_rejected_cleanly(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_definition_id = _create_job_definition_record(client, token, "handler-non-derived-work-job")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 409


def test_summaries_remain_consistent_after_handling(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_routed_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/handle-derived-work",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    assert job_run.result_summary["derived_work_handler"]["handler_category"] == "retry_handler"
    assert job_run.status == "pending"
