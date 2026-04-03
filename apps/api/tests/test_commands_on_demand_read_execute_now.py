from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from app.modules.readings.models import MeterReading, MeterReadingBatch, MeterRegisterSnapshot
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_on_demand_read_submission import (
    _submit_on_demand_read_command,
)
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _execute_on_demand_read_now(
    client,
    token: str,
    meter_id: str,
    *,
    command_template_id: str,
    endpoint_assignment_id: str,
    protocol_association_profile_id: str,
    on_demand_read_operation: str = "read_billing_snapshot",
    idempotency_key: str | None = None,
):
    return client.post(
        f"/api/v1/meters/{meter_id}/commands/on-demand-read/execute-now",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": command_template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_association_profile_id,
            "on_demand_read_operation": on_demand_read_operation,
            "priority": "high",
            "idempotency_key": idempotency_key,
            "notes": "On-demand-read execute now request",
            "execute_now_reason": "on-demand-read-execute-now",
        },
    )


def test_on_demand_read_execute_now_succeeds_from_valid_application_request(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-execute-now-success",
        category="on_demand_read",
    )

    response = _execute_on_demand_read_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-execute-now-success-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["execute_now_status"] == "executed"
    assert payload["result"]["command_status"] == "succeeded"
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == "billing"
    assert payload["result"]["on_demand_read_execution_outcome"] == "succeeded"
    assert payload["result"]["orchestration_artifact_present"] is True
    assert payload["result"]["terminalization_artifact_present"] is True
    assert payload["result"]["reused_existing_execute_now"] is False

    command = db_session.get(MeterCommand, UUID(payload["result"]["command_id"]))
    attempt = db_session.get(
        CommandExecutionAttempt,
        UUID(payload["result"]["command_execution_attempt_id"]),
    )
    assert command is not None
    assert attempt is not None
    assert command.current_status == CommandStatus.SUCCEEDED
    assert attempt.status == CommandExecutionAttemptStatus.SUCCEEDED
    assert (
        attempt.execution_metadata["on_demand_read_execute_now"][
            "runtime_on_demand_read_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_on_demand_read_execution"][
            "on_demand_read_execution_record_id"
        ]
    )
    batch_count = db_session.scalar(
        select(func.count())
        .select_from(MeterReadingBatch)
        .where(MeterReadingBatch.related_attempt_id == attempt.id)
    )
    snapshot_count = db_session.scalar(
        select(func.count())
        .select_from(MeterRegisterSnapshot)
        .where(MeterRegisterSnapshot.meter_id == command.meter_id)
    )
    reading_count = db_session.scalar(
        select(func.count())
        .select_from(MeterReading)
        .where(MeterReading.meter_id == command.meter_id)
    )
    assert batch_count == 1
    assert snapshot_count == 1
    assert reading_count >= 1


def test_on_demand_read_execute_now_is_idempotent_for_same_request_context(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-execute-now-repeat",
        category="on_demand_read",
    )

    first = _execute_on_demand_read_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-execute-now-repeat-1",
    )
    second = _execute_on_demand_read_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-execute-now-repeat-1",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["command_id"] == second.json()["result"]["command_id"]
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert (
        first.json()["result"]["runtime_on_demand_read_execution_record_id"]
        == second.json()["result"]["runtime_on_demand_read_execution_record_id"]
    )
    assert second.json()["result"]["reused_existing_execute_now"] is True


def test_on_demand_read_execute_now_refuses_when_submission_prerequisites_are_invalid(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-execute-now-wrong-template",
        category="profile_capture",
    )

    response = _execute_on_demand_read_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-execute-now-wrong-template-1",
    )

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_on_demand_read_execute_now_refuses_when_reused_command_is_not_execution_eligible(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-execute-now-ineligible",
        category="on_demand_read",
    )
    submit_response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-execute-now-ineligible-1",
    )
    assert submit_response.status_code == 200
    command_id = submit_response.json()["id"]
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()

    response = _execute_on_demand_read_now(
        client,
        token,
        meter_id,
        command_template_id=str(command.command_template_id),
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-execute-now-ineligible-1",
    )

    assert response.status_code == 409
    assert "not execution-eligible" in response.json()["detail"].lower()


def test_on_demand_read_execute_now_persists_compact_durable_linkage_artifact(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-execute-now-artifact",
        category="on_demand_read",
    )

    response = _execute_on_demand_read_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-execute-now-artifact-1",
    )

    assert response.status_code == 200
    payload = response.json()
    attempt = db_session.get(
        CommandExecutionAttempt,
        UUID(payload["result"]["command_execution_attempt_id"]),
    )
    command = db_session.get(MeterCommand, UUID(payload["result"]["command_id"]))
    assert attempt is not None
    assert command is not None
    job_run = db_session.get(JobRun, attempt.job_run_id)
    assert job_run is not None
    artifact = attempt.execution_metadata["on_demand_read_execute_now"]
    assert artifact["command_id"] == payload["result"]["command_id"]
    assert artifact["command_execution_attempt_id"] == payload["result"]["command_execution_attempt_id"]
    assert (
        artifact["runtime_on_demand_read_execution_record_id"]
        == payload["result"]["runtime_on_demand_read_execution_record_id"]
    )
    assert artifact["on_demand_read_operation"] == payload["result"]["on_demand_read_operation"]
    assert artifact["snapshot_type"] == payload["result"]["snapshot_type"]
    assert (
        artifact["on_demand_read_execution_outcome"]
        == payload["result"]["on_demand_read_execution_outcome"]
    )
    assert artifact["orchestration_artifact_present"] is True
    assert artifact["terminalization_artifact_present"] is True
    assert (
        command.result_summary["on_demand_read_execute_now"]["execute_now_identifier"]
        == artifact["execute_now_identifier"]
    )
    assert (
        job_run.result_summary["on_demand_read_execute_now"][
            "runtime_on_demand_read_execution_record_id"
        ]
        == artifact["runtime_on_demand_read_execution_record_id"]
    )
    assert attempt.execution_metadata["runtime_on_demand_read_materialization"]["materialized"] is True
    assert (
        attempt.execution_metadata["runtime_on_demand_read_materialization"]["persisted_snapshot_count"]
        == 1
    )
    assert job_run.status == JobRunStatus.SUCCEEDED
