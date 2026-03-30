from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_attempt_bootstrap import (
    _create_submitted_profile_capture_command,
)
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record
from tests.test_worker_runtime_executor_foundation import _create_load_profile_channel


def _execute_profile_capture_now(
    client,
    token: str,
    meter_id: str,
    *,
    command_template_id: str,
    endpoint_assignment_id: str,
    protocol_association_profile_id: str,
    channel_ids: list[str],
    idempotency_key: str | None = None,
):
    interval_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    interval_end = interval_start + timedelta(minutes=15)
    return client.post(
        f"/api/v1/meters/{meter_id}/commands/profile-capture/execute-now",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": command_template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_association_profile_id,
            "channel_ids": channel_ids,
            "interval_start": interval_start.isoformat(),
            "interval_end": interval_end.isoformat(),
            "priority": "high",
            "idempotency_key": idempotency_key,
            "notes": "Profile capture execute now request",
            "execute_now_reason": "profile-capture-execute-now",
        },
    )


def test_profile_capture_execute_now_succeeds_from_valid_application_request(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="profile-capture-execute-now-success",
        category="profile_capture",
    )

    response = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="profile-capture-execute-now-success-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["execute_now_status"] == "executed"
    assert payload["result"]["command_status"] == "succeeded"
    assert payload["result"]["terminal_status_category"] == "acknowledged"
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
        attempt.execution_metadata["profile_capture_execute_now"][
            "runtime_profile_read_execution_record_id"
        ]
        == attempt.execution_metadata["runtime_profile_read_execution"]["profile_read_execution_record_id"]
    )


def test_profile_capture_execute_now_is_idempotent_for_same_request_context(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="profile-capture-execute-now-repeat",
        category="profile_capture",
    )

    first = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="profile-capture-execute-now-repeat-1",
    )
    second = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="profile-capture-execute-now-repeat-1",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["command_id"] == second.json()["result"]["command_id"]
    assert (
        first.json()["result"]["command_execution_attempt_id"]
        == second.json()["result"]["command_execution_attempt_id"]
    )
    assert (
        first.json()["result"]["runtime_profile_read_execution_record_id"]
        == second.json()["result"]["runtime_profile_read_execution_record_id"]
    )
    assert second.json()["result"]["reused_existing_execute_now"] is True


def test_profile_capture_execute_now_refuses_when_submission_prerequisites_are_invalid(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="profile-capture-execute-now-wrong-template",
        category="on_demand_read",
    )

    response = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="profile-capture-execute-now-wrong-template-1",
    )

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_profile_capture_execute_now_refuses_when_reused_command_is_not_execution_eligible(
    client,
    db_session: Session,
) -> None:
    command_id, meter_id, endpoint_assignment_id, protocol_profile_id, channel_id = (
        _create_submitted_profile_capture_command(
            client,
            db_session,
            command_template_code="profile-capture-execute-now-ineligible",
            idempotency_key="profile-capture-execute-now-ineligible-1",
        )
    )
    command = db_session.get(MeterCommand, UUID(command_id))
    assert command is not None
    command.current_status = CommandStatus.SUCCEEDED
    db_session.add(command)
    db_session.commit()
    token = _login_as_super_admin(client, db_session)

    response = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=str(command.command_template_id),
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="profile-capture-execute-now-ineligible-1",
    )

    assert response.status_code == 409
    assert "not execution-eligible" in response.json()["detail"].lower()


def test_profile_capture_execute_now_persists_compact_durable_linkage_artifact(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="profile-capture-execute-now-artifact",
        category="profile_capture",
    )

    response = _execute_profile_capture_now(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="profile-capture-execute-now-artifact-1",
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
    artifact = attempt.execution_metadata["profile_capture_execute_now"]
    assert artifact["command_id"] == payload["result"]["command_id"]
    assert artifact["command_execution_attempt_id"] == payload["result"]["command_execution_attempt_id"]
    assert (
        artifact["runtime_profile_read_execution_record_id"]
        == payload["result"]["runtime_profile_read_execution_record_id"]
    )
    assert artifact["terminal_status_category"] == payload["result"]["terminal_status_category"]
    assert artifact["orchestration_artifact_present"] is True
    assert artifact["terminalization_artifact_present"] is True
    assert (
        command.result_summary["profile_capture_execute_now"]["execute_now_identifier"]
        == artifact["execute_now_identifier"]
    )
    assert (
        job_run.result_summary["profile_capture_execute_now"][
            "runtime_profile_read_execution_record_id"
        ]
        == artifact["runtime_profile_read_execution_record_id"]
    )
    assert job_run.status == JobRunStatus.SUCCEEDED
