from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.queue_serializers import RedisPlaceholderQueueSerializer
from app.runtime.services import build_queue_enqueue_payload
from app.runtime.services.dispatch_adapter import get_dispatch_request_projection
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_queue_enqueue_payload_serializes_into_stable_redis_placeholder_envelope_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    envelope = RedisPlaceholderQueueSerializer().serialize(payload)

    assert envelope.backend_name == "redis_placeholder"
    assert envelope.message_type == "derived_work_dispatch"
    assert envelope.payload_version == "v1"
    assert envelope.dispatch_category == "retry_dispatch_request"
    assert envelope.source_identifiers["job_run_id"] == job_run_id
    assert envelope.envelope_body["routing_key"] == "retry_dispatch_request"


def test_serializer_preserves_lineage_and_correlation(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    envelope = RedisPlaceholderQueueSerializer().serialize(payload)

    assert envelope.source_identifiers["command_id"] is not None
    assert envelope.source_identifiers["attempt_id"] is not None
    assert envelope.correlation_lineage["derived_correlation_id"] == dispatch_request.derived_correlation_id


def test_mock_default_path_remains_stable(client, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "queue_backend", "mock")
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["enqueue_result"]["enqueue_metadata"]["adapter"] == "mock_queue_adapter"


def test_repeated_enqueue_calls_stay_idempotent_for_redis_placeholder(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "queue_backend", "redis_placeholder")
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


def test_summaries_remain_consistent_after_backend_specific_serialization(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "queue_backend", "redis_placeholder")
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    envelope = job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["backend_message_envelope"]
    assert envelope["backend_name"] == "redis_placeholder"
    assert envelope["envelope_body"]["routing_key"] == "retry_dispatch_request"
