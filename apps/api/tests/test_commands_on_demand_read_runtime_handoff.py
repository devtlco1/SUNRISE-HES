from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandExecutionAttemptStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from tests.test_commands_on_demand_read_attempt_bootstrap import (
    _bootstrap_on_demand_read_attempt,
    _create_submitted_on_demand_read_command,
)


def _handoff_on_demand_read_to_runtime(
    client,
    command_id: str,
    *,
    handoff_identifier: str = "on-demand-read-handoff-1",
    executor_identifier: str = "worker-runtime-1",
):
    return client.post(
        f"/api/v1/internal/commands/{command_id}/handoff-on-demand-read-to-runtime",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "handoff_identifier": handoff_identifier,
            "executor_identifier": executor_identifier,
            "handoff_reason": "on-demand-read-runtime-handoff",
        },
    )


def _create_bootstrapped_on_demand_read_command(
    client,
    db_session: Session,
    *,
    command_template_code: str,
    idempotency_key: str,
) -> tuple[str, str]:
    command_id, _, _, _ = _create_submitted_on_demand_read_command(
        client,
        db_session,
        command_template_code=command_template_code,
        idempotency_key=idempotency_key,
    )
    bootstrap = _bootstrap_on_demand_read_attempt(client, command_id)
    assert bootstrap.status_code == 200
    return command_id, bootstrap.json()["result"]["command_execution_attempt_id"]


def _load_active_attempt(db_session: Session, command_id: str) -> CommandExecutionAttempt:
    attempt = db_session.scalar(
        select(CommandExecutionAttempt)
        .where(
            CommandExecutionAttempt.meter_command_id == UUID(command_id),
            CommandExecutionAttempt.ended_at.is_(None),
        )
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )
    assert attempt is not None
    return attempt


def test_on_demand_read_runtime_handoff_succeeds_from_valid_bootstrapped_attempt(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-success",
        idempotency_key="on-demand-read-runtime-handoff-success-1",
    )

    response = _handoff_on_demand_read_to_runtime(client, command_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["handoff_status"] == "handed_off"
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["result"]["runtime_on_demand_read_execution_present"] is True
    assert payload["result"]["runtime_on_demand_read_execution_record_id"] is not None
    assert payload["result"]["reused_existing_handoff"] is False
    assert payload["result"]["reused_existing_runtime_execution"] is False
    assert payload["job_run"]["id"] == payload["result"]["job_run_id"]

    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(payload["result"]["job_run_id"]))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["on_demand_read_runtime_handoff"]["handoff_identifier"]
        == "on-demand-read-handoff-1"
    )
    assert attempt.execution_metadata["runtime_on_demand_read_execution"]["status"] == "completed"
    assert (
        command.result_summary["on_demand_read_runtime_handoff"][
            "runtime_on_demand_read_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_on_demand_read_execution"][
            "on_demand_read_execution_record_id"
        ]
    )
    assert (
        job_run.result_summary["on_demand_read_runtime_handoff"][
            "runtime_on_demand_read_execution_present"
        ]
        is True
    )


def test_on_demand_read_runtime_handoff_refuses_when_bootstrap_artifact_is_missing(
    client,
    db_session: Session,
) -> None:
    command_id, _ = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-no-bootstrap",
        idempotency_key="on-demand-read-runtime-handoff-no-bootstrap-1",
    )
    attempt = _load_active_attempt(db_session, command_id)
    attempt.execution_metadata = {}
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_on_demand_read_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "bootstrap artifact" in response.json()["detail"].lower()


def test_on_demand_read_runtime_handoff_refuses_when_attempt_is_not_handoff_eligible(
    client,
    db_session: Session,
) -> None:
    command_id, _ = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-attempt-state",
        idempotency_key="on-demand-read-runtime-handoff-attempt-state-1",
    )
    attempt = _load_active_attempt(db_session, command_id)
    attempt.status = CommandExecutionAttemptStatus.RUNNING
    db_session.add(attempt)
    db_session.commit()

    response = _handoff_on_demand_read_to_runtime(client, command_id)

    assert response.status_code == 409
    assert "not runtime-handoff-eligible" in response.json()["detail"].lower()


def test_on_demand_read_runtime_handoff_refuses_when_normalized_payload_or_request_snapshot_is_incompatible(
    client,
    db_session: Session,
) -> None:
    missing_normalized_command_id, _ = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-missing-normalized",
        idempotency_key="on-demand-read-runtime-handoff-missing-normalized-1",
    )
    missing_normalized_command = db_session.get(MeterCommand, UUID(missing_normalized_command_id))
    assert missing_normalized_command is not None
    missing_normalized_command.normalized_payload = None
    db_session.add(missing_normalized_command)
    db_session.commit()

    missing_normalized_response = _handoff_on_demand_read_to_runtime(
        client,
        missing_normalized_command_id,
    )

    invalid_snapshot_command_id, _ = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-request-snapshot",
        idempotency_key="on-demand-read-runtime-handoff-request-snapshot-1",
    )
    invalid_snapshot_attempt = _load_active_attempt(db_session, invalid_snapshot_command_id)
    invalid_snapshot_attempt.request_snapshot = None
    db_session.add(invalid_snapshot_attempt)
    db_session.commit()

    invalid_snapshot_response = _handoff_on_demand_read_to_runtime(
        client,
        invalid_snapshot_command_id,
    )

    assert missing_normalized_response.status_code == 409
    assert "normalized payload" in missing_normalized_response.json()["detail"].lower()
    assert invalid_snapshot_response.status_code == 409
    assert "request snapshot" in invalid_snapshot_response.json()["detail"].lower()


def test_on_demand_read_runtime_handoff_refuses_when_endpoint_or_protocol_continuity_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    endpoint_command_id, _ = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-endpoint-mismatch",
        idempotency_key="on-demand-read-runtime-handoff-endpoint-mismatch-1",
    )
    endpoint_command = db_session.get(MeterCommand, UUID(endpoint_command_id))
    assert endpoint_command is not None
    endpoint_command.endpoint_assignment_id = None
    db_session.add(endpoint_command)
    db_session.commit()

    endpoint_response = _handoff_on_demand_read_to_runtime(client, endpoint_command_id)

    protocol_command_id, _ = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-protocol-mismatch",
        idempotency_key="on-demand-read-runtime-handoff-protocol-mismatch-1",
    )
    protocol_command = db_session.get(MeterCommand, UUID(protocol_command_id))
    assert protocol_command is not None
    protocol_command.protocol_association_profile_id = None
    db_session.add(protocol_command)
    db_session.commit()

    protocol_response = _handoff_on_demand_read_to_runtime(client, protocol_command_id)

    assert endpoint_response.status_code == 409
    assert "endpoint continuity" in endpoint_response.json()["detail"].lower()
    assert protocol_response.status_code == 409
    assert "protocol continuity" in protocol_response.json()["detail"].lower()


def test_on_demand_read_runtime_handoff_is_idempotent_for_same_context(
    client,
    db_session: Session,
) -> None:
    command_id, _ = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-repeat",
        idempotency_key="on-demand-read-runtime-handoff-repeat-1",
    )

    first = _handoff_on_demand_read_to_runtime(client, command_id)
    second = _handoff_on_demand_read_to_runtime(client, command_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["runtime_on_demand_read_execution_record_id"]
        == second.json()["result"]["runtime_on_demand_read_execution_record_id"]
    )
    assert first.json()["result"]["job_run_id"] == second.json()["result"]["job_run_id"]
    assert second.json()["result"]["reused_existing_handoff"] is True
    assert second.json()["result"]["reused_existing_runtime_execution"] is True


def test_on_demand_read_runtime_handoff_persists_durable_artifact_mapping(
    client,
    db_session: Session,
) -> None:
    command_id, attempt_id = _create_bootstrapped_on_demand_read_command(
        client,
        db_session,
        command_template_code="on-demand-read-runtime-handoff-artifact",
        idempotency_key="on-demand-read-runtime-handoff-artifact-1",
    )

    response = _handoff_on_demand_read_to_runtime(
        client,
        command_id,
        handoff_identifier="on-demand-read-runtime-handoff-artifact-1",
    )

    assert response.status_code == 200
    attempt = db_session.get(CommandExecutionAttempt, UUID(attempt_id))
    command = db_session.get(MeterCommand, UUID(command_id))
    job_run = db_session.get(JobRun, UUID(response.json()["result"]["job_run_id"]))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    artifact = attempt.execution_metadata["on_demand_read_runtime_handoff"]
    assert artifact["command_id"] == command_id
    assert artifact["command_execution_attempt_id"] == attempt_id
    assert artifact["handoff_identifier"] == "on-demand-read-runtime-handoff-artifact-1"
    assert artifact["on_demand_read_operation"] == "read_billing_snapshot"
    assert artifact["snapshot_type"] == "billing"
    assert artifact["runtime_on_demand_read_execution_present"] is True
    assert (
        command.result_summary["on_demand_read_runtime_handoff"][
            "runtime_on_demand_read_execution_record_id"
        ]
        == artifact["runtime_on_demand_read_execution_record_id"]
    )
    assert (
        job_run.result_summary["on_demand_read_runtime_handoff"]["handoff_identifier"]
        == artifact["handoff_identifier"]
    )
