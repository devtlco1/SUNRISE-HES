from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.contracts import QueuePayloadVersion
from app.runtime.queue_adapters import MockQueueAdapter
from app.runtime.services import build_queue_enqueue_payload
from app.runtime.services.dispatch_adapter import get_dispatch_request_projection
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_dispatch_request_serializes_into_stable_enqueue_payload_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)

    assert payload.payload_version == QueuePayloadVersion.V1
    assert payload.source_job_run_id == job_run_id
    assert payload.source_command_id is not None
    assert payload.source_attempt_id is not None
    assert payload.derived_correlation_id == dispatch_request.derived_correlation_id
    assert payload.serialized_payload["source"]["job_run_id"] == job_run_id
    assert payload.serialized_payload["dispatch_category"] == "retry_dispatch_request"


def test_default_mock_adapter_consumes_shared_payload_contract(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    result = MockQueueAdapter().enqueue(payload)

    assert result.enqueue_category.value == "retry_enqueue_result"
    assert result.enqueue_metadata["payload_version"] == "v1"
    assert result.enqueue_metadata["serialized_payload"]["source"]["job_run_id"] == job_run_id


def test_repeated_enqueue_calls_remain_idempotent_with_shared_payload(client, db_session: Session) -> None:
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
    assert first.json()["enqueue_result"]["adapter_receipt_id"] == second.json()["enqueue_result"]["adapter_receipt_id"]


def test_lineage_and_correlation_are_preserved_in_serialized_payload(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    serialized_payload = response.json()["enqueue_result"]["enqueue_metadata"]["serialized_payload"]
    assert serialized_payload["source"]["command_id"] is not None
    assert serialized_payload["source"]["attempt_id"] is not None
    assert serialized_payload["source"]["derived_correlation_id"] == response.json()["job_run"]["correlation_id"]


def test_enqueue_summary_remains_consistent_after_payload_serialization(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    assert job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["payload_version"] == "v1"
    assert job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["serialized_payload"]["dispatch_category"] == (
        "retry_dispatch_request"
    )
