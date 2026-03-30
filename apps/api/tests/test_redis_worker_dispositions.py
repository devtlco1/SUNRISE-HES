from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.broker_lifecycle import map_redis_semantics_to_lifecycle_contracts
from app.runtime.broker_semantics import map_envelope_to_redis_semantics
from app.runtime.queue_serializers import RedisPlaceholderQueueSerializer
from app.runtime.services import build_queue_enqueue_payload
from app.runtime.services.dispatch_adapter import get_dispatch_request_projection
from app.runtime.worker_consumption import map_lifecycle_to_worker_consumption
from app.runtime.worker_dispositions import map_worker_resolution_to_disposition_timeline
from app.runtime.worker_outcomes import map_worker_progress_to_outcome_timeline
from app.runtime.worker_progress import map_worker_state_to_progress_timeline
from app.runtime.worker_resolutions import map_worker_outcome_to_resolution_timeline
from app.runtime.worker_state import map_worker_consumption_to_state_timeline
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_redis_worker_resolution_timeline_maps_into_stable_worker_disposition_records_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    resolutions = map_worker_outcome_to_resolution_timeline(
        map_worker_progress_to_outcome_timeline(
            map_worker_state_to_progress_timeline(
                map_worker_consumption_to_state_timeline(
                    map_lifecycle_to_worker_consumption(
                        map_redis_semantics_to_lifecycle_contracts(
                            map_envelope_to_redis_semantics(RedisPlaceholderQueueSerializer().serialize(payload))
                        )
                    )
                )
            )
        )
    )
    dispositions = map_worker_resolution_to_disposition_timeline(resolutions)

    assert dispositions.records[0].disposition == "noop_disposition"
    assert dispositions.records[1].disposition == "archive_ready"
    assert dispositions.records[2].disposition == "retry_queue_ready"
    assert dispositions.records[3].disposition == "dead_letter_ready"
    assert dispositions.records[4].disposition == "cancellation_closed"


def test_archive_retry_dead_letter_and_cancellation_dispositions_are_exposed_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    dispositions = map_worker_resolution_to_disposition_timeline(
        map_worker_outcome_to_resolution_timeline(
            map_worker_progress_to_outcome_timeline(
                map_worker_state_to_progress_timeline(
                    map_worker_consumption_to_state_timeline(
                        map_lifecycle_to_worker_consumption(
                            map_redis_semantics_to_lifecycle_contracts(
                                map_envelope_to_redis_semantics(RedisPlaceholderQueueSerializer().serialize(payload))
                            )
                        )
                    )
                )
            )
        )
    )

    disposition_values = [record.disposition for record in dispositions.records]
    assert disposition_values == [
        "noop_disposition",
        "archive_ready",
        "retry_queue_ready",
        "dead_letter_ready",
        "cancellation_closed",
    ]


def test_lineage_and_correlation_are_preserved_through_worker_disposition_normalization(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    dispositions = map_worker_resolution_to_disposition_timeline(
        map_worker_outcome_to_resolution_timeline(
            map_worker_progress_to_outcome_timeline(
                map_worker_state_to_progress_timeline(
                    map_worker_consumption_to_state_timeline(
                        map_lifecycle_to_worker_consumption(
                            map_redis_semantics_to_lifecycle_contracts(
                                map_envelope_to_redis_semantics(RedisPlaceholderQueueSerializer().serialize(payload))
                            )
                        )
                    )
                )
            )
        )
    )

    assert dispositions.metadata["source_identifiers"]["job_run_id"] == job_run_id
    assert dispositions.metadata["source_identifiers"]["command_id"] is not None
    assert dispositions.metadata["correlation_lineage"]["derived_correlation_id"] == dispatch_request.derived_correlation_id


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


def test_repeated_enqueue_calls_stay_idempotent_with_worker_disposition_generation(
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


def test_summaries_remain_consistent_after_worker_disposition_generation(
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
    dispositions = job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["redis_worker_dispositions"]
    assert dispositions["records"][0]["disposition"] == "noop_disposition"
    assert dispositions["records"][1]["disposition"] == "archive_ready"
    assert dispositions["records"][3]["disposition"] == "dead_letter_ready"
