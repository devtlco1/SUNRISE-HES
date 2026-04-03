from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandCategory
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.readings.models import MeterReading, MeterReadingBatch, MeterRegisterSnapshot
from app.modules.readings.enums import SnapshotType
from tests.test_runtime_execution_session_heartbeat_foundation import (
    _persist_attempt_execution_metadata_sections,
    _prepare_runtime_relay_control_chain,
    _set_command_category,
)
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def _execute_runtime_on_demand_read_adapter(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-on-demand-read-adapter",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "execution_reason": "on-demand-read-adapter-contract",
        },
    )


def test_runtime_on_demand_read_adapter_executes_for_valid_billing_snapshot_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-on-demand-read-contract-success",
        mock_execution={
            "outcome": "succeeded",
            "register_snapshot": {
                "snapshot_type": "billing",
                "captured_at": "2026-03-27T00:00:00+00:00",
                "payload": {"1.0.1.8.0.255": "456.789"},
            },
        },
    )
    _set_command_category(
        db_session,
        command_id=command_id,
        category=CommandCategory.ON_DEMAND_READ,
    )

    response = _execute_runtime_on_demand_read_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["result"]["snapshot_type"] == SnapshotType.BILLING.value
    assert payload["result"]["execution_outcome"] == "succeeded"
    assert payload["result"]["adapter_acknowledgment_state"] == "accepted"
    assert payload["result"]["protocol_stage_outcome"] == "billing_snapshot_completed"
    assert payload["result"]["register_snapshot"]["payload"]["1.0.1.8.0.255"] == "456.789"
    assert payload["result"]["already_recorded"] is False

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert attempt is not None
    assert command is not None
    assert (
        attempt.execution_metadata["runtime_on_demand_read_execution"][
            "on_demand_read_execution_record_id"
        ]
        == payload["result"]["on_demand_read_execution_record_id"]
    )
    assert (
        command.result_summary["runtime_on_demand_read_execution"]["snapshot_type"]
        == SnapshotType.BILLING.value
    )
    batch_count = db_session.scalar(
        select(func.count())
        .select_from(MeterReadingBatch)
        .where(MeterReadingBatch.related_attempt_id == uuid.UUID(attempt_id))
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
    assert reading_count == 1


def test_runtime_on_demand_read_adapter_refuses_when_protocol_preparation_artifact_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-on-demand-read-contract-missing-dispatch-envelope",
    )
    _set_command_category(
        db_session,
        command_id=command_id,
        category=CommandCategory.ON_DEMAND_READ,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_dispatch_envelope"},
    )

    response = _execute_runtime_on_demand_read_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 409
    assert "dispatch envelope" in response.json()["detail"].lower()


def test_runtime_on_demand_read_adapter_refuses_when_session_chain_is_inconsistent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, _, _ = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-on-demand-read-contract-session-mismatch",
    )
    _set_command_category(
        db_session,
        command_id=command_id,
        category=CommandCategory.ON_DEMAND_READ,
    )

    response = _execute_runtime_on_demand_read_adapter(
        client,
        attempt_id,
        "different-session",
    )

    assert response.status_code == 409
    assert "does not match" in response.json()["detail"].lower()


def test_runtime_on_demand_read_adapter_is_idempotent_for_same_context(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-on-demand-read-contract-repeat",
    )
    _set_command_category(
        db_session,
        command_id=command_id,
        category=CommandCategory.ON_DEMAND_READ,
    )

    first = _execute_runtime_on_demand_read_adapter(client, attempt_id, session_identifier)
    second = _execute_runtime_on_demand_read_adapter(client, attempt_id, session_identifier)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["on_demand_read_execution_record_id"]
        == second.json()["result"]["on_demand_read_execution_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True
    batch_count = db_session.scalar(
        select(func.count())
        .select_from(MeterReadingBatch)
        .where(MeterReadingBatch.related_attempt_id == uuid.UUID(attempt_id))
    )
    assert batch_count == 1


def test_runtime_on_demand_read_adapter_refuses_for_non_on_demand_read_command_category(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-on-demand-read-contract-wrong-category",
        category=CommandCategory.REMOTE_DISCONNECT,
    )

    response = _execute_runtime_on_demand_read_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 409
    assert "only supports on-demand-read" in response.json()["detail"].lower()
