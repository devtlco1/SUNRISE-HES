from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.broker_lifecycle import map_redis_semantics_to_lifecycle_contracts
from app.runtime.broker_semantics import map_envelope_to_redis_semantics
from app.runtime.queue_serializers import RedisPlaceholderQueueSerializer
from app.runtime.services import build_queue_enqueue_payload
from app.runtime.services.dispatch_adapter import get_dispatch_request_projection
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_redis_queue_semantics_maps_into_stable_lifecycle_contracts_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    semantics = map_envelope_to_redis_semantics(RedisPlaceholderQueueSerializer().serialize(payload))
    lifecycle = map_redis_semantics_to_lifecycle_contracts(semantics)

    assert lifecycle.dequeue.consumer_name == "hes-worker-placeholder"
    assert lifecycle.dequeue.pending_message_id == semantics.receipt.message_id
    assert lifecycle.claim.claim_token.startswith("claim-token:")
    assert lifecycle.ack.ack_token.startswith("ack-token:")
    assert lifecycle.redelivery.dead_letter_stream == "hes:dispatch:dead-letter"


def test_claim_ack_and_redelivery_descriptors_are_exposed_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    lifecycle = map_redis_semantics_to_lifecycle_contracts(
        map_envelope_to_redis_semantics(RedisPlaceholderQueueSerializer().serialize(payload))
    )

    assert lifecycle.claim.claim_timeout_seconds == 300
    assert lifecycle.ack.consumer_group == "hes-worker-group"
    assert lifecycle.redelivery.retry_claim_hint is True
    assert lifecycle.redelivery.stale_claim_hint is False


def test_lineage_and_correlation_are_preserved_through_lifecycle_normalization(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    lifecycle = map_redis_semantics_to_lifecycle_contracts(
        map_envelope_to_redis_semantics(RedisPlaceholderQueueSerializer().serialize(payload))
    )

    assert lifecycle.metadata["source_identifiers"]["job_run_id"] == job_run_id
    assert lifecycle.metadata["source_identifiers"]["command_id"] is not None
    assert lifecycle.metadata["correlation_lineage"]["derived_correlation_id"] == dispatch_request.derived_correlation_id


def test_mock_default_behavior_remains_stable(client, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "queue_backend", "mock")
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["enqueue_result"]["enqueue_metadata"]["adapter"] == "mock_queue_adapter"


def test_repeated_enqueue_calls_stay_idempotent_with_lifecycle_normalization(
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


def test_summaries_remain_consistent_after_lifecycle_normalization(
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
    lifecycle = job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["redis_lifecycle"]
    assert lifecycle["dequeue"]["consumer_group"] == "hes-worker-group"
    assert lifecycle["ack"]["receipt_id"].startswith("redis-placeholder-receipt:")
