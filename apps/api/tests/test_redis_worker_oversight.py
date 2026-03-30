from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.broker_lifecycle import map_redis_semantics_to_lifecycle_contracts
from app.runtime.broker_semantics import map_envelope_to_redis_semantics
from app.runtime.queue_serializers import RedisPlaceholderQueueSerializer
from app.runtime.services import build_queue_enqueue_payload
from app.runtime.services.dispatch_adapter import get_dispatch_request_projection
from app.runtime.worker_audit_ledger import map_worker_reconciliation_to_audit_ledger
from app.runtime.worker_closure_reports import map_worker_finalization_to_closure_report
from app.runtime.worker_consumption import map_lifecycle_to_worker_consumption
from app.runtime.worker_control_plane import map_worker_governance_to_control_plane
from app.runtime.worker_dispositions import map_worker_resolution_to_disposition_timeline
from app.runtime.worker_finalizations import map_worker_disposition_to_finalization_timeline
from app.runtime.worker_governance import map_worker_audit_ledger_to_governance
from app.runtime.worker_outcomes import map_worker_progress_to_outcome_timeline
from app.runtime.worker_oversight import map_worker_control_plane_to_oversight
from app.runtime.worker_progress import map_worker_state_to_progress_timeline
from app.runtime.worker_reconciliation import (
    map_worker_closure_report_to_reconciliation_snapshot,
)
from app.runtime.worker_resolutions import map_worker_outcome_to_resolution_timeline
from app.runtime.worker_state import map_worker_consumption_to_state_timeline
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_redis_worker_control_plane_maps_into_stable_worker_oversight_records_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    control_plane = map_worker_governance_to_control_plane(
        map_worker_audit_ledger_to_governance(
            map_worker_reconciliation_to_audit_ledger(
                map_worker_closure_report_to_reconciliation_snapshot(
                    map_worker_finalization_to_closure_report(
                        map_worker_disposition_to_finalization_timeline(
                            map_worker_resolution_to_disposition_timeline(
                                map_worker_outcome_to_resolution_timeline(
                                    map_worker_progress_to_outcome_timeline(
                                        map_worker_state_to_progress_timeline(
                                            map_worker_consumption_to_state_timeline(
                                                map_lifecycle_to_worker_consumption(
                                                    map_redis_semantics_to_lifecycle_contracts(
                                                        map_envelope_to_redis_semantics(
                                                            RedisPlaceholderQueueSerializer().serialize(payload)
                                                        )
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
    )
    oversight = map_worker_control_plane_to_oversight(control_plane)

    assert oversight.records[0].oversight_type == "noop_oversight"
    assert oversight.records[1].oversight_type == "oversight_summary"
    assert oversight.records[2].oversight_type == "intervention_candidate_record"
    assert oversight.records[3].oversight_type == "operations_watch_note"
    assert oversight.records[4].oversight_type == "escalation_review_artifact"
    assert oversight.total_records == 5
    assert oversight.terminal_records == 4
    assert oversight.intervention_ready is True


def test_oversight_intervention_watch_and_escalation_artifacts_are_exposed_correctly(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    oversight = map_worker_control_plane_to_oversight(
        map_worker_governance_to_control_plane(
            map_worker_audit_ledger_to_governance(
                map_worker_reconciliation_to_audit_ledger(
                    map_worker_closure_report_to_reconciliation_snapshot(
                        map_worker_finalization_to_closure_report(
                            map_worker_disposition_to_finalization_timeline(
                                map_worker_resolution_to_disposition_timeline(
                                    map_worker_outcome_to_resolution_timeline(
                                        map_worker_progress_to_outcome_timeline(
                                            map_worker_state_to_progress_timeline(
                                                map_worker_consumption_to_state_timeline(
                                                    map_lifecycle_to_worker_consumption(
                                                        map_redis_semantics_to_lifecycle_contracts(
                                                            map_envelope_to_redis_semantics(
                                                                RedisPlaceholderQueueSerializer().serialize(payload)
                                                            )
                                                        )
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
    )

    oversight_values = [record.oversight_type for record in oversight.records]
    assert oversight_values == [
        "noop_oversight",
        "oversight_summary",
        "intervention_candidate_record",
        "operations_watch_note",
        "escalation_review_artifact",
    ]


def test_lineage_and_correlation_are_preserved_through_worker_oversight_normalization(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    dispatch_request = get_dispatch_request_projection(db_session, job_run_id=job_run_id)
    payload = build_queue_enqueue_payload(dispatch_request)
    oversight = map_worker_control_plane_to_oversight(
        map_worker_governance_to_control_plane(
            map_worker_audit_ledger_to_governance(
                map_worker_reconciliation_to_audit_ledger(
                    map_worker_closure_report_to_reconciliation_snapshot(
                        map_worker_finalization_to_closure_report(
                            map_worker_disposition_to_finalization_timeline(
                                map_worker_resolution_to_disposition_timeline(
                                    map_worker_outcome_to_resolution_timeline(
                                        map_worker_progress_to_outcome_timeline(
                                            map_worker_state_to_progress_timeline(
                                                map_worker_consumption_to_state_timeline(
                                                    map_lifecycle_to_worker_consumption(
                                                        map_redis_semantics_to_lifecycle_contracts(
                                                            map_envelope_to_redis_semantics(
                                                                RedisPlaceholderQueueSerializer().serialize(payload)
                                                            )
                                                        )
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
    )

    assert oversight.metadata["source_identifiers"]["job_run_id"] == job_run_id
    assert oversight.metadata["source_identifiers"]["command_id"] is not None
    assert oversight.metadata["correlation_lineage"]["derived_correlation_id"] == dispatch_request.derived_correlation_id


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


def test_repeated_enqueue_calls_stay_idempotent_with_worker_oversight_generation(
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


def test_summaries_remain_consistent_after_worker_oversight_generation(
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
    oversight = job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["redis_worker_oversight"]
    assert oversight["records"][0]["oversight_type"] == "noop_oversight"
    assert oversight["records"][1]["oversight_type"] == "oversight_summary"
    assert oversight["records"][3]["oversight_type"] == "operations_watch_note"
    assert oversight["total_records"] == 5
    assert oversight["intervention_ready"] is True
