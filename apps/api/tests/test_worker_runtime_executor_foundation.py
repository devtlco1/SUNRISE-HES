import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.connectivity.enums import ConnectivitySessionPurpose, ConnectivitySessionStatus
from app.modules.connectivity.models import ConnectivitySessionHistory
from app.modules.events.models import MeterEventIngestion
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.modules.readings.models import (
    LoadProfileInterval,
    MeterReading,
    MeterReadingBatch,
    MeterRegisterSnapshot,
)
from app.runtime.adapters.dlms_cosem import GuruxDlmsAdapterBridge
from app.runtime.contracts import (
    RuntimeCommandOutcome,
    RuntimeCommandResult,
    RuntimeSessionResult,
)


def _login_as_super_admin(client, db_session: Session) -> str:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"
    bootstrap_access_control(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_execute_runtime_plan_for_valid_attempt_using_placeholder_adapter(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-exec-success",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "succeeded"
    assert payload["plan"]["adapter_key"] == "gurux-dlms-bridge"
    assert payload["attempt"]["status"] == "succeeded"
    assert payload["session"]["status"] == "succeeded"
    assert payload["post_processing"]["outcome_category"] == "success"
    assert payload["post_processing"]["signals"]["should_retry"] is False

    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt is not None and attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert attempt.session_history_id is not None
    assert command is not None and command.current_status == "succeeded"
    assert command.result_summary["post_processing"]["outcome_category"] == "success"
    assert job_run is not None and job_run.status == "succeeded"


def test_runtime_executor_persists_reading_batch_readings_and_events(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    captured_at = datetime.now(UTC)
    attempt_id, command_id, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "succeeded",
            "reading_batch": {
                "source_type": "command_result",
                "captured_at": captured_at.isoformat(),
                "received_at": captured_at.isoformat(),
                "status": "received",
                "correlation_id": f"rt-ingest-{_suffix()}",
                "readings": [
                    {
                        "obis_code": "1.0.1.8.0.255",
                        "reading_type": "register",
                        "value_numeric": "123.456",
                        "unit": "kWh",
                        "captured_at": captured_at.isoformat(),
                    }
                ],
            },
            "events": [
                {
                    "event_code": "power_restore",
                    "event_name": "Power Restore",
                    "severity": "info",
                    "event_state": "open",
                    "occurred_at": captured_at.isoformat(),
                    "normalized_payload": {"reason": "manual_test"},
                }
            ],
        },
        command_template_code="runtime-exec-telemetry",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    batch_id = payload["ingested_batch"]["id"]
    session_id = payload["session"]["id"]
    assert len(payload["ingested_batch"]["readings"]) == 1
    assert len(payload["ingested_events"]) == 1

    batch = db_session.get(MeterReadingBatch, batch_id)
    assert batch is not None
    assert str(batch.related_command_id) == command_id
    assert str(batch.related_attempt_id) == attempt_id
    assert str(batch.session_history_id) == session_id

    readings = db_session.query(MeterReading).filter(MeterReading.batch_id == batch.id).all()
    events = db_session.query(MeterEventIngestion).filter(MeterEventIngestion.related_batch_id == batch.id).all()
    assert len(readings) == 1
    assert len(events) == 1


def test_runtime_executor_persists_register_snapshot(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    captured_at = datetime.now(UTC)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "succeeded",
            "reading_batch": {
                "source_type": "command_result",
                "captured_at": captured_at.isoformat(),
                "status": "received",
                "register_snapshots": [
                    {
                        "snapshot_type": "billing",
                        "captured_at": captured_at.isoformat(),
                        "payload": {"1.0.1.8.0.255": "456.789"},
                    }
                ],
            },
        },
        command_template_code="runtime-exec-snapshot",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    batch_id = response.json()["ingested_batch"]["id"]
    snapshots = db_session.query(MeterRegisterSnapshot).filter(
        MeterRegisterSnapshot.related_batch_id == batch_id
    ).all()
    assert len(snapshots) == 1
    assert snapshots[0].payload["1.0.1.8.0.255"] == "456.789"


def test_runtime_executor_persists_load_profile_intervals_and_skips_duplicates(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, meter_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-exec-intervals",
        max_retries=0,
        return_meter_id=True,
    )
    channel_id = _create_load_profile_channel(client, token, meter_id)
    interval_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    interval_end = interval_start + timedelta(minutes=15)

    current_attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    assert current_attempt is not None
    command = db_session.get(MeterCommand, current_attempt.meter_command_id)
    assert command is not None
    command.request_payload = {
        "mock_execution": {
            "outcome": "succeeded",
            "reading_batch": {
                "source_type": "command_result",
                "captured_at": interval_start.isoformat(),
                "status": "received",
                "load_profile_intervals": [
                    {
                        "channel_id": channel_id,
                        "interval_start": interval_start.isoformat(),
                        "interval_end": interval_end.isoformat(),
                        "value_numeric": "11.5",
                        "quality": "good",
                    },
                    {
                        "channel_id": channel_id,
                        "interval_start": interval_start.isoformat(),
                        "interval_end": interval_end.isoformat(),
                        "value_numeric": "11.5",
                        "quality": "good",
                    },
                ],
            },
        }
    }
    command.normalized_payload = command.request_payload
    db_session.add(command)
    db_session.commit()

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted_interval_count"] == 1
    assert payload["skipped_duplicate_interval_count"] == 1

    intervals = db_session.query(LoadProfileInterval).filter(
        LoadProfileInterval.channel_id == channel_id
    ).all()
    assert len(intervals) == 1


def test_execute_runtime_plan_creates_and_finalizes_connectivity_session_history(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded", "bytes_sent": 144, "bytes_received": 288},
        command_template_code="runtime-exec-session",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    session_id = response.json()["session"]["id"]
    session_history = db_session.get(ConnectivitySessionHistory, session_id)
    assert session_history is not None
    assert session_history.status == ConnectivitySessionStatus.SUCCEEDED
    assert session_history.session_purpose == ConnectivitySessionPurpose.MANUAL_DIAGNOSTIC
    assert session_history.started_at is not None
    assert session_history.ended_at is not None
    assert session_history.bytes_sent == 144
    assert session_history.bytes_received == 288


def test_execute_runtime_plan_synchronizes_failure_statuses(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "MOCK_FAILURE",
            "error_message": "Placeholder adapter failure",
        },
        command_template_code="runtime-exec-failure",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "failed"
    assert payload["attempt"]["status"] == "failed"
    assert payload["session"]["status"] == "failed"

    attempt = db_session.get(CommandExecutionAttempt, attempt_id)
    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert attempt is not None and attempt.status == CommandExecutionAttemptStatus.FAILED
    assert command is not None and command.current_status == "failed"
    assert job_run is not None and job_run.status == "failed"


def test_runtime_executor_applies_retryable_failure_policy(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "NO_ROUTE",
            "error_message": "Transport path unavailable",
        },
        command_template_code="runtime-exec-retryable-failure",
        max_retries=2,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["post_processing"]["outcome_category"] == "retryable_failure"
    assert payload["post_processing"]["retry"]["should_retry"] is True

    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert command is not None and command.current_status == "retry_wait"
    assert job_run is not None and job_run.status == "pending"


def test_runtime_executor_applies_permanent_failure_policy(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={
            "outcome": "failed",
            "error_code": "AUTH_FAILED",
            "error_message": "Association rejected",
        },
        command_template_code="runtime-exec-permanent-failure",
        max_retries=2,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["post_processing"]["outcome_category"] == "permanent_failure"
    assert payload["post_processing"]["retry"]["should_retry"] is False

    command = db_session.get(MeterCommand, command_id)
    job_run = db_session.get(JobRun, job_run_id)
    assert command is not None and command.current_status == "failed"
    assert job_run is not None and job_run.status == "failed"


def test_reject_execution_when_runtime_plan_context_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt_without_runtime_context(
        client,
        db_session,
        token,
        command_template_code="runtime-exec-missing",
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "endpoint assignment" in response.json()["detail"].lower()


def test_executor_uses_adapter_boundary(monkeypatch, client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-exec-adapter-boundary",
        max_retries=0,
    )
    called = {"used": False}

    def fake_execute(self, plan):  # noqa: ANN001
        called["used"] = True
        now = datetime.now(UTC)
        return RuntimeCommandResult(
            outcome=RuntimeCommandOutcome.SUCCEEDED,
            result_summary={"adapter": "patched"},
            response_snapshot={"adapter": "patched"},
            session_result=RuntimeSessionResult(
                status=ConnectivitySessionStatus.SUCCEEDED,
                session_purpose=plan.session_purpose,
                started_at=now,
                ended_at=now,
                bytes_sent=1,
                bytes_received=2,
            ),
        )

    monkeypatch.setattr(GuruxDlmsAdapterBridge, "execute", fake_execute)

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    assert called["used"] is True
    assert response.json()["response_snapshot"]["adapter"] == "patched"


def _create_started_attempt(
    client,
    db_session: Session,
    token: str,
    *,
    mock_execution: dict[str, object],
    command_template_code: str,
    max_retries: int,
    return_meter_id: bool = False,
    grant_runtime_coordination: bool = True,
) -> tuple[str, str, str] | tuple[str, str, str, str]:
    from tests.test_jobs_scheduler_foundation import (
        _create_job_definition_record,
        _create_manual_job_run_record,
    )
    from tests.test_protocol_runtime_foundation import (
        _attach_runtime_connectivity,
        _create_meter_record,
    )

    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_record(
        client,
        token,
        command_template_code,
        max_retries=max_retries,
    )

    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_profile_id,
            "idempotency_key": f"runtime-exec-{_suffix()}",
            "request_payload": {"mock_execution": mock_execution},
        },
    )
    assert command_response.status_code == 201
    command_id = command_response.json()["id"]

    job_definition_id = _create_job_definition_record(client, token, f"runtime-job-{_suffix()}")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    claim_response = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "limit": 10, "lease_seconds": 60},
    )
    assert claim_response.status_code == 200

    start_attempt = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "meter_command_id": command_id},
    )
    assert start_attempt.status_code == 200
    if grant_runtime_coordination:
        _grant_runtime_coordination_records(
            db_session,
            attempt_id=start_attempt.json()["id"],
            command_id=command_id,
            job_run_id=job_run_id,
            executor_identifier="worker-runtime-1",
        )
    if return_meter_id:
        return start_attempt.json()["id"], command_id, job_run_id, meter_id
    return start_attempt.json()["id"], command_id, job_run_id


def _create_started_attempt_without_runtime_context(
    client,
    db_session: Session,
    token: str,
    *,
    command_template_code: str,
) -> tuple[str, str, str]:
    from tests.test_jobs_scheduler_foundation import (
        _create_job_definition_record,
        _create_manual_job_run_record,
        _create_meter_record,
    )

    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, command_template_code, max_retries=0)

    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "idempotency_key": f"runtime-missing-{_suffix()}",
        },
    )
    assert command_response.status_code == 201

    job_definition_id = _create_job_definition_record(client, token, f"runtime-missing-job-{_suffix()}")
    job_run_id = _create_manual_job_run_record(client, token, job_definition_id)

    claim_response = client.post(
        "/api/v1/internal/job-runs/claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "limit": 10, "lease_seconds": 60},
    )
    assert claim_response.status_code == 200

    start_attempt = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/start-command-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "worker-runtime-1", "meter_command_id": command_response.json()["id"]},
    )
    assert start_attempt.status_code == 200
    _grant_runtime_coordination_records(
        db_session,
        attempt_id=start_attempt.json()["id"],
        command_id=command_response.json()["id"],
        job_run_id=job_run_id,
        executor_identifier="worker-runtime-1",
    )
    return start_attempt.json()["id"], command_response.json()["id"], job_run_id


def _create_command_template_record(client, token: str, code: str, *, max_retries: int) -> str:
    response = client.post(
        "/api/v1/command-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "name": code.replace("-", " ").title(),
            "category": "on_demand_read",
            "target_scope": "meter",
            "timeout_seconds": 120,
            "max_retries": max_retries,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_load_profile_channel(client, token: str, meter_id: str) -> str:
    response = client.post(
        f"/api/v1/meters/{meter_id}/load-profile-channels",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel_code": f"rt-lp-{_suffix()}",
            "obis_code": "1.0.99.1.0.255",
            "unit": "kWh",
            "interval_seconds": 900,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _suffix() -> str:
    return str(int(datetime.now(UTC).timestamp() * 1000))


def _grant_runtime_coordination_records(
    db_session: Session,
    *,
    attempt_id: str,
    command_id: str,
    job_run_id: str,
    executor_identifier: str,
) -> None:
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert job_run is not None
    now = datetime.now(UTC)
    lease_expires_at = now + timedelta(minutes=5)
    dispatch_request_identity = f"{job_run_id}:runtime-test-dispatch"
    handoff_record = {
        "status": "handed_off",
        "backend_name": "redis",
        "handoff_record_id": f"runtime-test-handoff:{attempt_id}",
        "stream_name": "hes:test:dispatch",
        "consumer_group": "hes-test-worker-group",
        "consumer_name": f"hes-worker:{executor_identifier}",
        "worker_identifier": executor_identifier,
        "job_run_id": job_run_id,
        "related_command_id": command_id,
        "command_attempt_id": attempt_id,
        "handed_off_at": now.isoformat(),
        "job_run_claimed": False,
        "command_materialized": False,
        "attempt_started": True,
        "summary": "Synthetic runtime handoff for guarded execute-runtime-plan tests.",
        "lineage": {
            "dispatch_request_identity": dispatch_request_identity,
            "queue_message_id": f"runtime-test-message:{attempt_id}",
            "claim_token": f"runtime-test-claim:{attempt_id}",
            "source_identifiers": {
                "job_run_id": job_run_id,
                "command_id": command_id,
                "attempt_id": attempt_id,
            },
            "correlation_lineage": {
                "source_correlation_id": job_run.correlation_id,
                "derived_correlation_id": job_run.correlation_id,
            },
            "dispatch_metadata": {"synthetic": True},
            "intended_worker_path": "runtime_test_worker_path",
        },
    }
    lease_record = {
        "status": "leased",
        "lease_record_id": f"runtime-test-lease:{attempt_id}",
        "executor_identifier": executor_identifier,
        "job_run_id": job_run_id,
        "related_command_id": command_id,
        "command_attempt_id": attempt_id,
        "leased_at": now.isoformat(),
        "lease_expires_at": lease_expires_at.isoformat(),
        "reused_existing_lease": False,
        "summary": "Synthetic runtime lease for guarded execute-runtime-plan tests.",
        "lineage": {
            "handoff_record_id": handoff_record["handoff_record_id"],
            "dispatch_request_identity": dispatch_request_identity,
            "queue_message_id": handoff_record["lineage"]["queue_message_id"],
            "claim_token": handoff_record["lineage"]["claim_token"],
            "source_identifiers": handoff_record["lineage"]["source_identifiers"],
            "correlation_lineage": handoff_record["lineage"]["correlation_lineage"],
            "dispatch_metadata": handoff_record["lineage"]["dispatch_metadata"],
            "intended_worker_path": handoff_record["lineage"]["intended_worker_path"],
        },
    }
    invocation_record = {
        "status": "authorized",
        "invocation_record_id": f"runtime-test-invocation:{attempt_id}",
        "executor_identifier": executor_identifier,
        "job_run_id": job_run_id,
        "related_command_id": command_id,
        "command_attempt_id": attempt_id,
        "invoked_at": now.isoformat(),
        "gate_expires_at": lease_expires_at.isoformat(),
        "reused_existing_invocation": False,
        "summary": "Synthetic runtime invocation gate for guarded execute-runtime-plan tests.",
        "lineage": {
            "handoff_record_id": handoff_record["handoff_record_id"],
            "lease_record_id": lease_record["lease_record_id"],
            "dispatch_request_identity": dispatch_request_identity,
            "queue_message_id": handoff_record["lineage"]["queue_message_id"],
            "claim_token": handoff_record["lineage"]["claim_token"],
            "source_identifiers": handoff_record["lineage"]["source_identifiers"],
            "correlation_lineage": handoff_record["lineage"]["correlation_lineage"],
            "dispatch_metadata": handoff_record["lineage"]["dispatch_metadata"],
            "intended_worker_path": handoff_record["lineage"]["intended_worker_path"],
        },
    }
    guard_record = {
        "guard_record_id": f"runtime-test-guard:{attempt_id}",
        "executor_identifier": executor_identifier,
        "attempt_id": attempt_id,
        "lease_record_id": lease_record["lease_record_id"],
        "invocation_record_id": invocation_record["invocation_record_id"],
        "execution_started_at": now.isoformat(),
        "guard_expires_at": lease_expires_at.isoformat(),
        "dispatch_request_identity": dispatch_request_identity,
        "queue_message_id": handoff_record["lineage"]["queue_message_id"],
        "claim_token": handoff_record["lineage"]["claim_token"],
    }
    attempt.execution_metadata = {
        **(attempt.execution_metadata or {}),
        "queue_runtime_handoff": handoff_record,
        "runtime_execution_lease": lease_record,
        "runtime_execution_invocation_gate": invocation_record,
        "runtime_execution_guard": guard_record,
    }
    job_run.result_summary = {
        **(job_run.result_summary or {}),
        "runtime_execution_handoff": handoff_record,
        "runtime_execution_lease": lease_record,
        "runtime_execution_invocation_gate": invocation_record,
        "runtime_execution_guard": guard_record,
    }
    db_session.add_all([attempt, job_run])
    db_session.commit()
