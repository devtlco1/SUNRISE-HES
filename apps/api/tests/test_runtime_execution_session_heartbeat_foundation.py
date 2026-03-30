from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.commands.enums import CommandCategory
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.connectivity.enums import (
    AssociationAuthenticationMode,
    ConnectivityTransportType,
    ProtocolFamily,
)
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.adapters.dlms_cosem import (
    _build_gurux_relay_control_execution_audit_summary,
    _interpret_gurux_relay_control_stub_response,
    _map_relay_control_operation_to_gurux_definition,
    _normalize_gurux_relay_control_request,
    _project_gurux_relay_control_terminal_adapter_status,
    _project_gurux_relay_control_execution_phase_state,
    _resolve_gurux_relay_control_transport_profile,
    _validate_gurux_relay_control_target_object,
    GuruxRelayControlInvocationStubResponse,
)
from app.runtime.contracts import (
    MeterRuntimeTarget,
    RuntimeCommandOutcome,
    RuntimeExecutionContext,
    RuntimeExecutionSessionLineage,
    RuntimeRelayControlAdapterRequest,
    RuntimeRelayControlOperation,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from tests.test_worker_runtime_executor_foundation import (
    _create_started_attempt,
    _login_as_super_admin,
)


def _start_runtime_execution_session(client, attempt_id: str):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )


def _finalize_runtime_execution_session(client, attempt_id: str, session_identifier: str):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _record_runtime_execution_outcome(client, attempt_id: str, session_identifier: str):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
            "outcome_reason": "placeholder-terminal-disposition",
            "summary_message": "Placeholder runtime session completed cleanly.",
        },
    )


def _bridge_runtime_execution_outcome_to_attempt(client, attempt_id: str, session_identifier: str):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_attempt_disposition_to_post_processing(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-attempt-disposition-to-post-processing",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_post_processing_to_follow_up_materialization(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-post-processing-to-follow-up-materialization",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_follow_up_materialization_to_operational_closure(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-follow-up-materialization-to-operational-closure",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_operational_closure_to_protocol_execution_intent(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-operational-closure-to-protocol-execution-intent",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_protocol_execution_intent_to_adapter_selection(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-protocol-execution-intent-to-adapter-selection",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-protocol-adapter-selection-to-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_protocol_dispatch_request_to_invocation_result(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-protocol-dispatch-request-to-invocation-result",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_protocol_invocation_result_to_execution_observation(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-protocol-invocation-result-to-execution-observation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_protocol_execution_observation_to_interpretation(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-protocol-execution-observation-to-interpretation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_protocol_interpretation_to_reconciliation(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-protocol-interpretation-to-reconciliation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-protocol-reconciliation-to-terminal-settlement",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_terminal_settlement_to_closure_attestation(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-terminal-settlement-to-closure-attestation",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_closure_attestation_to_publication_contract(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-closure-attestation-to-publication-contract",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_publication_contract_to_externalization_envelope(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-publication-contract-to-externalization-envelope",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_externalization_envelope_to_delivery_contract(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-externalization-envelope-to-delivery-contract",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _bridge_runtime_delivery_contract_to_dispatch_envelope(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-delivery-contract-to-dispatch-envelope",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _execute_runtime_relay_control_adapter(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-relay-control-adapter",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _persist_attempt_execution_metadata_sections(
    db_session: Session,
    attempt_id: str,
    *,
    section_updates: dict[str, dict[str, object]] | None = None,
    removed_sections: set[str] | None = None,
) -> CommandExecutionAttempt:
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    execution_metadata = dict(attempt.execution_metadata or {})
    for section in removed_sections or set():
        execution_metadata.pop(section, None)
    for section, updates in (section_updates or {}).items():
        current_section = dict(execution_metadata.get(section) or {})
        current_section.update(updates)
        execution_metadata[section] = current_section
    attempt.execution_metadata = execution_metadata
    db_session.add(attempt)
    db_session.commit()
    return attempt


def _set_command_category(
    db_session: Session,
    *,
    command_id: str,
    category: CommandCategory,
) -> MeterCommand:
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert command is not None
    template = command.command_template
    assert template is not None
    template.category = category
    db_session.add(template)
    db_session.commit()
    db_session.refresh(command)
    return command


def _prepare_runtime_relay_control_chain(
    client,
    db_session: Session,
    token: str,
    *,
    command_template_code: str,
    category: CommandCategory = CommandCategory.REMOTE_DISCONNECT,
    mock_execution: dict[str, object] | None = None,
) -> tuple[str, str, str, str]:
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution=mock_execution or {"outcome": "succeeded"},
        command_template_code=command_template_code,
        max_retries=0,
    )
    _set_command_category(
        db_session,
        command_id=command_id,
        category=category,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    return attempt_id, command_id, job_run_id, session_identifier


def test_runtime_execution_session_start_succeeds_with_valid_coordination_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-start-success",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "active"
    assert payload["result"]["executor_identifier"] == "worker-runtime-1"
    assert payload["result"]["heartbeat_refreshed"] is False

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert attempt.execution_metadata["runtime_execution_session"]["executor_identifier"] == (
        "worker-runtime-1"
    )
    assert command.result_summary["runtime_execution_session"]["executor_identifier"] == (
        "worker-runtime-1"
    )
    assert job_run.result_summary["runtime_execution_session"]["executor_identifier"] == (
        "worker-runtime-1"
    )


def test_runtime_execution_session_start_bounds_expiry_by_minimum_prerequisite(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-min-expiry",
        max_retries=0,
    )
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    now = datetime.now(UTC)
    lease_expires_at = (now + timedelta(seconds=40)).isoformat()
    gate_expires_at = (now + timedelta(seconds=20)).isoformat()
    guard_expires_at = (now + timedelta(seconds=30)).isoformat()
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"lease_expires_at": lease_expires_at},
            "runtime_execution_invocation_gate": {"gate_expires_at": gate_expires_at},
            "runtime_execution_guard": {"guard_expires_at": guard_expires_at},
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1", "session_timeout_seconds": 60},
    )

    assert response.status_code == 200
    assert response.json()["result"]["session_expires_at"] == gate_expires_at


def test_runtime_execution_session_start_refuses_when_no_lease_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-no-lease",
        max_retries=0,
        grant_runtime_coordination=False,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "active runtime lease" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_no_invocation_gate_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-no-gate",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_execution_invocation_gate"},
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "invocation gate" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_no_guard_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-no-guard",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_execution_guard"},
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "execution guard" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-lease-mismatch",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"executor_identifier": "another-executor"}
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "lease is owned by another executor" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_invocation_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-gate-mismatch",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "executor_identifier": "another-executor"
            }
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "invocation gate is owned by another executor" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_guard_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-guard-mismatch",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {"executor_identifier": "another-executor"}
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "guard is owned by another executor" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_lease_is_expired(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-lease-expired",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {
                "lease_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            }
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "lease is expired" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_invocation_gate_is_expired(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-gate-expired",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "gate_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            }
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "invocation gate is expired" in response.json()["detail"].lower()


def test_runtime_execution_session_start_refuses_when_guard_is_expired(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-guard-expired",
        max_retries=0,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {
                "guard_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            }
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert response.status_code == 409
    assert "guard is expired" in response.json()["detail"].lower()


def test_repeated_runtime_execution_session_start_reuses_same_active_session(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-repeat",
        max_retries=0,
    )

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["session_identifier"] == second.json()["result"]["session_identifier"]
    assert second.json()["result"]["reused_existing_session"] is True


def test_runtime_execution_session_heartbeat_refreshes_same_active_executor_session(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-heartbeat-success",
        max_retries=0,
    )

    start = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1", "session_timeout_seconds": 30},
    )
    session_identifier = start.json()["result"]["session_identifier"]
    first_heartbeat_at = start.json()["result"]["last_heartbeat_at"]
    first_expiry = start.json()["result"]["session_expires_at"]

    heartbeat = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/heartbeat-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "session_timeout_seconds": 45,
        },
    )

    assert start.status_code == 200
    assert heartbeat.status_code == 200
    assert heartbeat.json()["result"]["session_identifier"] == session_identifier
    assert heartbeat.json()["result"]["heartbeat_refreshed"] is True
    assert heartbeat.json()["result"]["last_heartbeat_at"] != first_heartbeat_at
    assert heartbeat.json()["result"]["session_expires_at"] >= first_expiry
    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    assert attempt is not None
    lease_expires_at = datetime.fromisoformat(
        attempt.execution_metadata["runtime_execution_lease"]["lease_expires_at"]
    )
    gate_expires_at = datetime.fromisoformat(
        attempt.execution_metadata["runtime_execution_invocation_gate"]["gate_expires_at"]
    )
    guard_expires_at = datetime.fromisoformat(
        attempt.execution_metadata["runtime_execution_guard"]["guard_expires_at"]
    )
    session_expires_at = datetime.fromisoformat(heartbeat.json()["result"]["session_expires_at"])
    assert session_expires_at <= min(lease_expires_at, gate_expires_at, guard_expires_at)


def test_runtime_execution_session_heartbeat_refuses_when_lease_expires_even_if_guard_remains_active(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-heartbeat-lease-expired",
        max_retries=0,
    )

    start = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )
    session_identifier = start.json()["result"]["session_identifier"]

    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {
                "lease_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            },
            "runtime_execution_invocation_gate": {
                "gate_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            },
            "runtime_execution_guard": {
                "guard_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            },
        },
    )

    heartbeat = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/heartbeat-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert heartbeat.status_code == 409
    assert "lease is expired" in heartbeat.json()["detail"].lower()


def test_runtime_execution_session_heartbeat_refuses_when_gate_expires_even_if_guard_remains_active(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-heartbeat-gate-expired",
        max_retries=0,
    )

    start = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )
    session_identifier = start.json()["result"]["session_identifier"]

    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {
                "lease_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            },
            "runtime_execution_invocation_gate": {
                "gate_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            },
            "runtime_execution_guard": {
                "guard_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            },
        },
    )

    heartbeat = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/heartbeat-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert heartbeat.status_code == 409
    assert "invocation gate is expired" in heartbeat.json()["detail"].lower()


def test_runtime_execution_session_heartbeat_refuses_when_guard_expires(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-heartbeat-guard-expired",
        max_retries=0,
    )

    start = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )
    session_identifier = start.json()["result"]["session_identifier"]

    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {
                "lease_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            },
            "runtime_execution_invocation_gate": {
                "gate_expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            },
            "runtime_execution_guard": {
                "guard_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            },
        },
    )

    heartbeat = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/heartbeat-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert heartbeat.status_code == 409
    assert "guard is expired" in heartbeat.json()["detail"].lower()


def test_runtime_execution_session_heartbeat_refuses_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-heartbeat-ownership",
        max_retries=0,
    )

    start = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )
    session_identifier = start.json()["result"]["session_identifier"]

    heartbeat = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/heartbeat-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "another-executor",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert heartbeat.status_code == 409
    assert "lease is owned by another executor" in heartbeat.json()["detail"].lower()


def test_runtime_execution_session_heartbeat_refuses_expired_session(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-heartbeat-expired",
        max_retries=0,
    )

    start = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/start-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"executor_identifier": "worker-runtime-1"},
    )
    session_identifier = start.json()["result"]["session_identifier"]

    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_session": {
                "session_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            }
        },
    )

    heartbeat = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/heartbeat-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert heartbeat.status_code == 409
    assert "session is expired" in heartbeat.json()["detail"].lower()


def test_runtime_execution_session_finalize_succeeds_with_valid_active_session(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]

    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "finalize_reason": "placeholder-session-complete",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert finalize.json()["result"]["status"] == "finalized"
    assert finalize.json()["result"]["finalized_by_executor_identifier"] == "worker-runtime-1"
    assert finalize.json()["result"]["finalize_reason"] == "placeholder-session-complete"

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert job_run is not None
    assert attempt.execution_metadata["runtime_execution_session"]["status"] == "finalized"
    assert job_run.result_summary["runtime_execution_session"]["status"] == "finalized"


def test_runtime_execution_session_finalize_refuses_when_no_session_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-no-session",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": "missing-session",
        },
    )

    assert response.status_code == 409
    assert "active runtime session" in response.json()["detail"].lower()


def test_runtime_execution_session_finalize_refuses_when_session_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-session-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]

    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "another-executor",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 409
    assert "session is owned by another executor" in finalize.json()["detail"].lower()


def test_runtime_execution_session_finalize_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-lease-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"executor_identifier": "another-executor"}
        },
    )

    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 409
    assert "lease is owned by another executor" in finalize.json()["detail"].lower()


def test_runtime_execution_session_finalize_refuses_when_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-gate-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "executor_identifier": "another-executor"
            }
        },
    )

    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 409
    assert "invocation gate is owned by another executor" in finalize.json()["detail"].lower()


def test_runtime_execution_session_finalize_refuses_when_guard_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-guard-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {"executor_identifier": "another-executor"}
        },
    )

    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 409
    assert "guard is owned by another executor" in finalize.json()["detail"].lower()


def test_runtime_execution_session_finalize_refuses_when_session_is_expired(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-expired",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_session": {
                "session_expires_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
            }
        },
    )

    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 409
    assert "session is expired" in finalize.json()["detail"].lower()


def test_runtime_execution_session_finalize_refuses_when_session_identifier_mismatches(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-id-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)

    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": "wrong-session-id",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 409
    assert "does not match the active runtime session" in finalize.json()["detail"].lower()


def test_repeated_runtime_execution_session_finalize_is_idempotent_for_same_executor_session(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-finalize-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["session_identifier"] == second.json()["result"]["session_identifier"]
    assert second.json()["result"]["already_finalized"] is True


def test_runtime_execution_session_heartbeat_refuses_after_finalize(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-session-heartbeat-after-finalize",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    heartbeat = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/heartbeat-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert heartbeat.status_code == 409
    assert "already finalized" in heartbeat.json()["detail"].lower()


def test_runtime_execution_outcome_records_for_finalized_session(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-record-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "finalize_reason": "placeholder-session-complete",
        },
    )

    outcome = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
            "outcome_reason": "placeholder-terminal-disposition",
            "summary_message": "Placeholder runtime session completed cleanly.",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    payload = outcome.json()
    assert payload["result"]["status"] == "recorded"
    assert payload["result"]["terminal_outcome"] == "completed"
    assert payload["result"]["outcome_recorded_by_executor_identifier"] == "worker-runtime-1"

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert command is not None
    assert job_run is not None
    assert attempt.execution_metadata["runtime_execution_outcome"]["terminal_outcome"] == (
        "completed"
    )
    assert command.result_summary["runtime_execution_outcome"]["terminal_outcome"] == (
        "completed"
    )
    assert job_run.result_summary["runtime_execution_outcome"]["terminal_outcome"] == (
        "completed"
    )


def test_runtime_execution_outcome_refuses_when_no_session_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-no-session",
        max_retries=0,
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": "missing-session",
            "terminal_outcome": "completed",
        },
    )

    assert response.status_code == 409
    assert "finalized runtime session" in response.json()["detail"].lower()


def test_runtime_execution_outcome_refuses_when_session_is_not_finalized(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-session-not-finalized",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
        },
    )

    assert start.status_code == 200
    assert response.status_code == 409
    assert "finalized runtime session" in response.json()["detail"].lower()


def test_runtime_execution_outcome_refuses_when_session_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-session-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "another-executor",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert response.status_code == 409
    assert "session is owned by another executor" in response.json()["detail"].lower()


def test_runtime_execution_outcome_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-lease-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"executor_identifier": "another-executor"}
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert response.status_code == 409
    assert "lease is owned by another executor" in response.json()["detail"].lower()


def test_runtime_execution_outcome_refuses_when_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-gate-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "executor_identifier": "another-executor"
            }
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert response.status_code == 409
    assert "invocation gate is owned by another executor" in response.json()["detail"].lower()


def test_runtime_execution_outcome_refuses_when_guard_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-guard-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {"executor_identifier": "another-executor"}
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert response.status_code == 409
    assert "guard is owned by another executor" in response.json()["detail"].lower()


def test_runtime_execution_outcome_refuses_when_session_identifier_mismatches(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-session-id-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    response = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": "wrong-finalized-session",
            "terminal_outcome": "completed",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert response.status_code == 409
    assert "does not match the finalized runtime session" in response.json()["detail"].lower()


def test_repeated_runtime_execution_outcome_recording_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-outcome-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/finalize-execution-session",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
            "outcome_reason": "placeholder-repeat",
        },
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/record-execution-outcome",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "terminal_outcome": "completed",
            "outcome_reason": "placeholder-repeat",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["outcome_record_id"] == second.json()["result"]["outcome_record_id"]
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_attempt_disposition_bridge_succeeds_for_finalized_session_with_recorded_outcome(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-bridge-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
            "disposition_reason": "placeholder-attempt-finalized",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 200
    assert bridge.json()["result"]["mapped_attempt_status"] == "succeeded"

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert attempt.status.value == "succeeded"
    assert attempt.ended_at is not None
    assert attempt.execution_metadata["runtime_attempt_disposition"]["terminal_outcome"] == (
        "completed"
    )
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    assert meter_command is not None
    assert meter_command.current_status.value == "succeeded"
    assert job_run is not None
    assert job_run.status.value == "succeeded"


def test_runtime_attempt_disposition_bridge_refuses_when_no_recorded_outcome_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-no-outcome",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert bridge.status_code == 409
    assert "recorded runtime execution outcome" in bridge.json()["detail"].lower()


def test_runtime_attempt_disposition_bridge_refuses_when_session_is_not_finalized(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-session-not-finalized",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert outcome.status_code == 409
    assert bridge.status_code == 409
    assert "finalized runtime session" in bridge.json()["detail"].lower()


def test_runtime_attempt_disposition_bridge_refuses_when_outcome_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-outcome-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_outcome": {"executor_identifier": "another-executor"}
        },
    )

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 409
    assert "outcome is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_attempt_disposition_bridge_refuses_when_session_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-session-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "another-executor",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 409
    assert "session is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_attempt_disposition_bridge_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-lease-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"executor_identifier": "another-executor"}
        },
    )

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 409
    assert "lease is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_attempt_disposition_bridge_refuses_when_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-gate-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "executor_identifier": "another-executor"
            }
        },
    )

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 409
    assert "invocation gate is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_attempt_disposition_bridge_refuses_when_guard_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-guard-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {"executor_identifier": "another-executor"}
        },
    )

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 409
    assert "guard is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_attempt_disposition_bridge_refuses_when_session_identifier_mismatches_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-session-id-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": "wrong-session-chain",
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 409
    assert "does not match the finalized runtime session" in bridge.json()["detail"].lower()


def test_repeated_runtime_attempt_disposition_bridge_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-disposition-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)

    first = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )
    second = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-execution-outcome-to-attempt",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["disposition_record_id"]
        == second.json()["result"]["disposition_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_post_processing_bridge_succeeds_for_valid_disposition_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-bridge-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    disposition = _bridge_runtime_execution_outcome_to_attempt(
        client, attempt_id, session_identifier
    )

    bridge = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert disposition.status_code == 200
    assert bridge.status_code == 200
    payload = bridge.json()
    assert payload["result"]["status"] == "bridged"
    assert payload["result"]["downstream_state"] == "completed_no_followup"
    assert payload["result"]["signals"]["should_retry"] is False

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert attempt.execution_metadata["runtime_post_processing_bridge"]["downstream_state"] == (
        "completed_no_followup"
    )
    assert meter_command.result_summary["runtime_post_processing_bridge"]["downstream_state"] == (
        "completed_no_followup"
    )
    assert job_run.result_summary["runtime_post_processing_bridge"]["downstream_state"] == (
        "completed_no_followup"
    )


def test_runtime_post_processing_bridge_refuses_when_no_attempt_disposition_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-no-disposition",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    finalize = _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    outcome = _record_runtime_execution_outcome(client, attempt_id, session_identifier)

    bridge = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert finalize.status_code == 200
    assert outcome.status_code == 200
    assert bridge.status_code == 409
    assert "recorded runtime attempt disposition" in bridge.json()["detail"].lower()


def test_runtime_post_processing_bridge_refuses_when_attempt_disposition_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-disposition-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_attempt_disposition": {"executor_identifier": "another-executor"}
        },
    )

    bridge = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert bridge.status_code == 409
    assert "attempt disposition is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_post_processing_bridge_refuses_when_outcome_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-outcome-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_outcome": {"executor_identifier": "another-executor"}
        },
    )

    bridge = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert bridge.status_code == 409
    assert "outcome is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_post_processing_bridge_refuses_when_session_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-session-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)

    bridge = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-attempt-disposition-to-post-processing",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "another-executor",
            "session_identifier": session_identifier,
        },
    )

    assert bridge.status_code == 409
    assert "session is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_post_processing_bridge_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-lease-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"executor_identifier": "another-executor"}
        },
    )

    bridge = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert bridge.status_code == 409
    assert "lease is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_post_processing_bridge_refuses_when_invocation_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-gate-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "executor_identifier": "another-executor"
            }
        },
    )

    bridge = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert bridge.status_code == 409
    assert "invocation gate is owned by another executor" in bridge.json()["detail"].lower()


def test_runtime_post_processing_bridge_refuses_when_execution_guard_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-guard-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {"executor_identifier": "another-executor"}
        },
    )

    bridge = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert bridge.status_code == 409
    assert "guard is owned by another executor" in bridge.json()["detail"].lower()


def test_repeated_runtime_post_processing_bridge_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-post-processing-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)

    first = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["post_processing_record_id"]
        == second.json()["result"]["post_processing_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_follow_up_materialization_succeeds_for_valid_post_processing_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-materialization-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 200
    payload = materialize.json()
    assert payload["result"]["status"] == "materialized"
    assert len(payload["result"]["follow_up_descriptors"]) >= 2
    assert (
        payload["result"]["follow_up_descriptors"][0]["descriptor_type"]
        == "terminal_summary_ready"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_follow_up_materialization"]["status"]
        == "materialized"
    )
    assert (
        meter_command.result_summary["runtime_follow_up_materialization"]["status"]
        == "materialized"
    )
    assert (
        job_run.result_summary["runtime_follow_up_materialization"]["status"]
        == "materialized"
    )


def test_runtime_follow_up_materialization_refuses_when_no_post_processing_bridge_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-no-post-processing",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 409
    assert "recorded runtime post-processing bridge" in materialize.json()["detail"].lower()


def test_runtime_follow_up_materialization_refuses_when_post_processing_bridge_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-post-processing-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_post_processing_bridge": {
                "executor_identifier": "another-executor"
            }
        },
    )

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 409
    assert "post-processing bridge is owned by another executor" in materialize.json()["detail"].lower()


def test_runtime_follow_up_materialization_refuses_when_attempt_disposition_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-disposition-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_attempt_disposition": {"executor_identifier": "another-executor"}
        },
    )

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 409
    assert "attempt disposition is owned by another executor" in materialize.json()["detail"].lower()


def test_runtime_follow_up_materialization_refuses_when_outcome_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-outcome-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_outcome": {"executor_identifier": "another-executor"}
        },
    )

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 409
    assert "outcome is owned by another executor" in materialize.json()["detail"].lower()


def test_runtime_follow_up_materialization_refuses_when_session_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-session-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    materialize = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-post-processing-to-follow-up-materialization",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "another-executor",
            "session_identifier": session_identifier,
        },
    )

    assert materialize.status_code == 409
    assert "session is owned by another executor" in materialize.json()["detail"].lower()


def test_runtime_follow_up_materialization_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-lease-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"executor_identifier": "another-executor"}
        },
    )

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 409
    assert "lease is owned by another executor" in materialize.json()["detail"].lower()


def test_runtime_follow_up_materialization_refuses_when_invocation_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-gate-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "executor_identifier": "another-executor"
            }
        },
    )

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 409
    assert "invocation gate is owned by another executor" in materialize.json()["detail"].lower()


def test_runtime_follow_up_materialization_refuses_when_execution_guard_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-guard-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {"executor_identifier": "another-executor"}
        },
    )

    materialize = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert materialize.status_code == 409
    assert "guard is owned by another executor" in materialize.json()["detail"].lower()


def test_repeated_runtime_follow_up_materialization_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-follow-up-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["materialization_record_id"]
        == second.json()["result"]["materialization_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_operational_closure_records_for_valid_follow_up_materialization_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 200
    payload = closure.json()
    assert payload["result"]["status"] == "recorded"
    assert "terminal_summary_ready" in payload["result"]["included_follow_up_descriptor_types"]

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_operational_closure"]["status"] == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_operational_closure"]["status"] == "recorded"
    )
    assert job_run.result_summary["runtime_operational_closure"]["status"] == "recorded"


def test_runtime_operational_closure_refuses_when_no_follow_up_materialization_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-no-materialization",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "recorded runtime follow-up materialization" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_follow_up_materialization_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-materialization-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_follow_up_materialization": {
                "executor_identifier": "another-executor"
            }
        },
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "follow-up materialization is owned by another executor" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_post_processing_bridge_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-post-processing-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_post_processing_bridge": {
                "executor_identifier": "another-executor"
            }
        },
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "post-processing bridge is owned by another executor" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_attempt_disposition_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-disposition-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_attempt_disposition": {"executor_identifier": "another-executor"}
        },
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "attempt disposition is owned by another executor" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_outcome_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-outcome-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_outcome": {"executor_identifier": "another-executor"}
        },
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "outcome is owned by another executor" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_session_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-session-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    closure = client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/bridge-follow-up-materialization-to-operational-closure",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "another-executor",
            "session_identifier": session_identifier,
        },
    )

    assert closure.status_code == 409
    assert "session is owned by another executor" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_lease_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-lease-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_lease": {"executor_identifier": "another-executor"}
        },
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "lease is owned by another executor" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_invocation_gate_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-gate-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_invocation_gate": {
                "executor_identifier": "another-executor"
            }
        },
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "invocation gate is owned by another executor" in closure.json()["detail"].lower()


def test_runtime_operational_closure_refuses_when_execution_guard_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-guard-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_execution_guard": {"executor_identifier": "another-executor"}
        },
    )

    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 409
    assert "guard is owned by another executor" in closure.json()["detail"].lower()


def test_repeated_runtime_operational_closure_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-operational-closure-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["closure_record_id"]
        == second.json()["result"]["closure_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_protocol_execution_intent_derives_for_valid_operational_closure_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-intent-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    closure = _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    intent = _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    assert closure.status_code == 200
    assert intent.status_code == 200
    payload = intent.json()
    assert payload["result"]["status"] == "derived"
    assert (
        payload["result"]["protocol_execution_intent_type"]
        == "placeholder_protocol_adapter_ready"
    )
    assert (
        payload["result"]["target_execution_mode"]
        == "deferred_protocol_execution_boundary"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_protocol_execution_intent"]["status"]
        == "derived"
    )
    assert (
        meter_command.result_summary["runtime_protocol_execution_intent"]["status"]
        == "derived"
    )
    assert job_run.result_summary["runtime_protocol_execution_intent"]["status"] == "derived"


def test_runtime_protocol_execution_intent_refuses_when_no_operational_closure_exists(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-intent-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )

    intent = _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert intent.status_code == 409
    assert "recorded runtime operational closure" in intent.json()["detail"].lower()


def test_runtime_protocol_execution_intent_refuses_when_operational_closure_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-intent-closure-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_operational_closure": {
                "executor_identifier": "another-executor",
                "closure_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    intent = _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    assert intent.status_code == 409
    assert "operational closure is owned by another executor" in intent.json()["detail"].lower()


def test_runtime_protocol_execution_intent_refuses_when_follow_up_materialization_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-intent-materialization-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_follow_up_materialization": {
                "executor_identifier": "another-executor",
                "materialized_by_executor_identifier": "another-executor",
            }
        },
    )

    intent = _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    assert intent.status_code == 409
    assert "follow-up materialization is owned by another executor" in intent.json()["detail"].lower()


def test_repeated_runtime_protocol_execution_intent_derivation_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-intent-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["intent_record_id"]
        == second.json()["result"]["intent_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_protocol_adapter_selection_resolves_for_valid_protocol_execution_intent_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-adapter-selection-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    selection = _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    assert selection.status_code == 200
    payload = selection.json()
    assert payload["result"]["status"] == "resolved"
    assert (
        payload["result"]["adapter_family"]
        == "placeholder_protocol_boundary_adapter"
    )
    assert (
        payload["result"]["capability_profile"]
        == "placeholder_protocol_dispatch_shape_ready"
    )
    assert payload["result"]["selected_adapter_key"] == "placeholder.protocol.boundary.adapter"
    assert (
        "supports_placeholder_relay_control"
        in payload["result"]["supported_placeholder_capabilities"]
    )
    assert (
        "supports_placeholder_read_profile"
        in payload["result"]["supported_placeholder_capabilities"]
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_protocol_adapter_selection"]["status"]
        == "resolved"
    )
    assert (
        meter_command.result_summary["runtime_protocol_adapter_selection"]["status"]
        == "resolved"
    )
    assert (
        job_run.result_summary["runtime_protocol_adapter_selection"]["status"]
        == "resolved"
    )


def test_runtime_protocol_adapter_selection_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-adapter-selection-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )

    selection = _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert selection.status_code == 409
    assert "recorded runtime protocol execution intent" in selection.json()["detail"].lower()


def test_runtime_protocol_adapter_selection_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-adapter-selection-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    selection = _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    assert selection.status_code == 409
    assert "recorded runtime operational closure" in selection.json()["detail"].lower()


def test_runtime_protocol_adapter_selection_refuses_when_protocol_execution_intent_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-adapter-selection-intent-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_protocol_execution_intent": {
                "executor_identifier": "another-executor",
                "intent_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    selection = _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    assert selection.status_code == 409
    assert "protocol execution intent is owned by another executor" in selection.json()["detail"].lower()


def test_repeated_runtime_protocol_adapter_selection_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-adapter-selection-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["selection_record_id"]
        == second.json()["result"]["selection_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_protocol_dispatch_request_assembles_for_valid_adapter_selection_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-dispatch-request-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    dispatch_request = _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    assert dispatch_request.status_code == 200
    payload = dispatch_request.json()
    assert payload["result"]["status"] == "assembled"
    assert (
        payload["result"]["request_family"]
        == "placeholder_protocol_execution_request"
    )
    assert (
        payload["result"]["execution_envelope"]["action_type"]
        == "placeholder_protocol_invocation_shape_ready"
    )
    assert (
        payload["result"]["execution_envelope"]["schema_version"]
        == "placeholder-runtime-protocol-dispatch-request.v1"
    )
    assert (
        payload["result"]["execution_envelope"]["adapter_family"]
        == "placeholder_protocol_boundary_adapter"
    )
    assert (
        payload["result"]["execution_envelope"]["capability_profile"]
        == "placeholder_protocol_dispatch_shape_ready"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_protocol_dispatch_request"]["status"]
        == "assembled"
    )
    assert (
        meter_command.result_summary["runtime_protocol_dispatch_request"]["status"]
        == "assembled"
    )
    assert (
        job_run.result_summary["runtime_protocol_dispatch_request"]["status"]
        == "assembled"
    )


def test_runtime_protocol_dispatch_request_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-dispatch-request-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )

    dispatch_request = _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert dispatch_request.status_code == 409
    assert "recorded runtime protocol adapter selection" in dispatch_request.json()["detail"].lower()


def test_runtime_protocol_dispatch_request_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-dispatch-request-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    dispatch_request = _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    assert dispatch_request.status_code == 409
    assert "recorded runtime protocol execution intent" in dispatch_request.json()["detail"].lower()


def test_runtime_protocol_dispatch_request_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-dispatch-request-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    dispatch_request = _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    assert dispatch_request.status_code == 409
    assert "recorded runtime operational closure" in dispatch_request.json()["detail"].lower()


def test_runtime_protocol_dispatch_request_refuses_when_adapter_selection_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-dispatch-request-selection-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_protocol_adapter_selection": {
                "executor_identifier": "another-executor",
                "selection_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    dispatch_request = _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    assert dispatch_request.status_code == 409
    assert "protocol adapter selection is owned by another executor" in dispatch_request.json()["detail"].lower()


def test_repeated_runtime_protocol_dispatch_request_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-dispatch-request-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["dispatch_request_record_id"]
        == second.json()["result"]["dispatch_request_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_protocol_invocation_result_records_for_valid_dispatch_request_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-invocation-result-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    invocation_result = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    assert invocation_result.status_code == 200
    payload = invocation_result.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["result_family"]
        == "placeholder_protocol_invocation_result"
    )
    assert (
        payload["result"]["invocation_payload"]["acknowledgment_state"]
        == "placeholder_protocol_invocation_acknowledged"
    )
    assert (
        payload["result"]["invocation_payload"]["schema_version"]
        == "placeholder-runtime-protocol-invocation-result.v1"
    )
    assert (
        payload["result"]["invocation_payload"]["adapter_family"]
        == "placeholder_protocol_boundary_adapter"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_protocol_invocation_result"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_protocol_invocation_result"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_protocol_invocation_result"]["status"]
        == "recorded"
    )


def test_runtime_protocol_invocation_result_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-invocation-result-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )

    invocation_result = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert invocation_result.status_code == 409
    assert "recorded runtime protocol dispatch request" in invocation_result.json()["detail"].lower()


def test_runtime_protocol_invocation_result_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-invocation-result-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    invocation_result = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    assert invocation_result.status_code == 409
    assert "recorded runtime protocol adapter selection" in invocation_result.json()["detail"].lower()


def test_runtime_protocol_invocation_result_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-invocation-result-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    invocation_result = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    assert invocation_result.status_code == 409
    assert "recorded runtime protocol execution intent" in invocation_result.json()["detail"].lower()


def test_runtime_protocol_invocation_result_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-invocation-result-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    invocation_result = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    assert invocation_result.status_code == 409
    assert "recorded runtime operational closure" in invocation_result.json()["detail"].lower()


def test_runtime_protocol_invocation_result_refuses_when_dispatch_request_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-invocation-result-dispatch-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_protocol_dispatch_request": {
                "executor_identifier": "another-executor",
                "request_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    invocation_result = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    assert invocation_result.status_code == 409
    assert "protocol dispatch request is owned by another executor" in invocation_result.json()["detail"].lower()


def test_repeated_runtime_protocol_invocation_result_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-invocation-result-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["invocation_result_record_id"]
        == second.json()["result"]["invocation_result_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_protocol_execution_observation_records_for_valid_invocation_result_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    observation = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert observation.status_code == 200
    payload = observation.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["observation_family"]
        == "placeholder_protocol_execution_observation"
    )
    assert (
        payload["result"]["observation_payload"]["normalization_state"]
        == "placeholder_protocol_response_normalized"
    )
    assert (
        payload["result"]["observation_payload"]["schema_version"]
        == "placeholder-runtime-protocol-execution-observation.v1"
    )
    assert (
        payload["result"]["observation_payload"]["adapter_family"]
        == "placeholder_protocol_boundary_adapter"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_protocol_execution_observation"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_protocol_execution_observation"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_protocol_execution_observation"]["status"]
        == "recorded"
    )


def test_runtime_protocol_execution_observation_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )

    observation = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert observation.status_code == 409
    assert "recorded runtime protocol invocation result" in observation.json()["detail"].lower()


def test_runtime_protocol_execution_observation_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    observation = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert observation.status_code == 409
    assert "recorded runtime protocol dispatch request" in observation.json()["detail"].lower()


def test_runtime_protocol_execution_observation_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    observation = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert observation.status_code == 409
    assert "recorded runtime protocol adapter selection" in observation.json()["detail"].lower()


def test_runtime_protocol_execution_observation_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    observation = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert observation.status_code == 409
    assert "recorded runtime protocol execution intent" in observation.json()["detail"].lower()


def test_runtime_protocol_execution_observation_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    observation = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert observation.status_code == 409
    assert "recorded runtime operational closure" in observation.json()["detail"].lower()


def test_runtime_protocol_execution_observation_refuses_when_invocation_result_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-invocation-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_protocol_invocation_result": {
                "executor_identifier": "another-executor",
                "result_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    observation = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert observation.status_code == 409
    assert "protocol invocation result is owned by another executor" in observation.json()["detail"].lower()


def test_repeated_runtime_protocol_execution_observation_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-execution-observation-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["observation_record_id"]
        == second.json()["result"]["observation_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_protocol_interpretation_records_for_valid_execution_observation_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert interpretation.status_code == 200
    payload = interpretation.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["interpretation_family"]
        == "placeholder_protocol_terminal_interpretation"
    )
    assert (
        payload["result"]["interpretation_payload"]["interpretation_state"]
        == "placeholder_runtime_interpretation_recorded"
    )
    assert (
        payload["result"]["interpretation_payload"]["schema_version"]
        == "placeholder-runtime-protocol-interpretation.v1"
    )
    assert (
        payload["result"]["interpretation_payload"]["semantic_outcome_classification"]
        == "placeholder_terminal_meaning_ready"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_protocol_interpretation"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_protocol_interpretation"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_protocol_interpretation"]["status"]
        == "recorded"
    )


def test_runtime_protocol_interpretation_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert interpretation.status_code == 409
    assert "recorded runtime protocol execution observation" in interpretation.json()["detail"].lower()


def test_runtime_protocol_interpretation_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert interpretation.status_code == 409
    assert "recorded runtime protocol invocation result" in interpretation.json()["detail"].lower()


def test_runtime_protocol_interpretation_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert interpretation.status_code == 409
    assert "recorded runtime protocol dispatch request" in interpretation.json()["detail"].lower()


def test_runtime_protocol_interpretation_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert interpretation.status_code == 409
    assert "recorded runtime protocol adapter selection" in interpretation.json()["detail"].lower()


def test_runtime_protocol_interpretation_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert interpretation.status_code == 409
    assert "recorded runtime protocol execution intent" in interpretation.json()["detail"].lower()


def test_runtime_protocol_interpretation_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert interpretation.status_code == 409
    assert "recorded runtime operational closure" in interpretation.json()["detail"].lower()


def test_runtime_protocol_interpretation_refuses_when_execution_observation_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-observation-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_protocol_execution_observation": {
                "executor_identifier": "another-executor",
                "observation_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    interpretation = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert interpretation.status_code == 409
    assert "protocol execution observation is owned by another executor" in interpretation.json()["detail"].lower()


def test_repeated_runtime_protocol_interpretation_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-interpretation-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["interpretation_record_id"]
        == second.json()["result"]["interpretation_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_protocol_reconciliation_records_for_valid_interpretation_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 200
    payload = reconciliation.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["reconciliation_family"]
        == "placeholder_protocol_runtime_reconciliation"
    )
    assert (
        payload["result"]["reconciliation_payload"]["reconciliation_state"]
        == "placeholder_runtime_reconciliation_recorded"
    )
    assert (
        payload["result"]["reconciliation_payload"]["schema_version"]
        == "placeholder-runtime-protocol-reconciliation.v1"
    )
    assert (
        payload["result"]["reconciliation_payload"][
            "runtime_semantic_reconciliation_classification"
        ]
        == "placeholder_protocol_meaning_reconciled"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_protocol_reconciliation"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_protocol_reconciliation"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_protocol_reconciliation"]["status"]
        == "recorded"
    )


def test_runtime_protocol_reconciliation_refuses_when_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-no-interpretation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert start.status_code == 200
    assert reconciliation.status_code == 409
    assert "recorded runtime protocol interpretation" in reconciliation.json()["detail"].lower()


def test_runtime_protocol_reconciliation_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 409
    assert "recorded runtime protocol execution observation" in reconciliation.json()["detail"].lower()


def test_runtime_protocol_reconciliation_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 409
    assert "recorded runtime protocol invocation result" in reconciliation.json()["detail"].lower()


def test_runtime_protocol_reconciliation_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 409
    assert "recorded runtime protocol dispatch request" in reconciliation.json()["detail"].lower()


def test_runtime_protocol_reconciliation_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 409
    assert "recorded runtime protocol adapter selection" in reconciliation.json()["detail"].lower()


def test_runtime_protocol_reconciliation_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 409
    assert "recorded runtime protocol execution intent" in reconciliation.json()["detail"].lower()


def test_runtime_protocol_reconciliation_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 409
    assert "recorded runtime operational closure" in reconciliation.json()["detail"].lower()


def test_runtime_protocol_reconciliation_refuses_when_interpretation_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-interpretation-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_protocol_interpretation": {
                "executor_identifier": "another-executor",
                "interpretation_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    reconciliation = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert reconciliation.status_code == 409
    assert "protocol interpretation is owned by another executor" in reconciliation.json()["detail"].lower()


def test_repeated_runtime_protocol_reconciliation_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-protocol-reconciliation-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["reconciliation_record_id"]
        == second.json()["result"]["reconciliation_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_terminal_settlement_records_for_valid_reconciliation_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 200
    payload = settlement.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["settlement_family"]
        == "placeholder_terminal_runtime_settlement"
    )
    assert (
        payload["result"]["settlement_payload"]["settlement_state"]
        == "placeholder_terminal_runtime_settlement_recorded"
    )
    assert (
        payload["result"]["settlement_payload"]["schema_version"]
        == "placeholder-runtime-terminal-settlement.v1"
    )
    assert (
        payload["result"]["settlement_payload"][
            "terminal_runtime_settlement_classification"
        ]
        == "placeholder_final_runtime_projection_ready"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_terminal_settlement"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_terminal_settlement"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_terminal_settlement"]["status"]
        == "recorded"
    )


def test_runtime_terminal_settlement_refuses_when_protocol_reconciliation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-reconciliation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime protocol reconciliation" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-interpretation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_interpretation"},
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime protocol interpretation" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime protocol execution observation" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime protocol invocation result" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime protocol dispatch request" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime protocol adapter selection" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime protocol execution intent" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "recorded runtime operational closure" in settlement.json()["detail"].lower()


def test_runtime_terminal_settlement_refuses_when_reconciliation_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-reconciliation-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_protocol_reconciliation": {
                "executor_identifier": "another-executor",
                "reconciliation_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    settlement = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert settlement.status_code == 409
    assert "protocol reconciliation is owned by another executor" in settlement.json()["detail"].lower()


def test_repeated_runtime_terminal_settlement_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-terminal-settlement-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["settlement_record_id"]
        == second.json()["result"]["settlement_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_closure_attestation_records_for_valid_terminal_settlement_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 200
    payload = attestation.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["attestation_family"]
        == "placeholder_runtime_closure_attestation"
    )
    assert (
        payload["result"]["attestation_payload"]["attestation_state"]
        == "placeholder_runtime_closure_attested"
    )
    assert (
        payload["result"]["attestation_payload"]["schema_version"]
        == "placeholder-runtime-closure-attestation.v1"
    )
    assert (
        payload["result"]["attestation_payload"]["closure_attestation_classification"]
        == "placeholder_externally_consumable_finalization_ready"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_closure_attestation"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_closure_attestation"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_closure_attestation"]["status"]
        == "recorded"
    )


def test_runtime_closure_attestation_refuses_when_terminal_settlement_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-settlement",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime terminal settlement" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_protocol_reconciliation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-reconciliation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_reconciliation"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime protocol reconciliation" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-interpretation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_interpretation"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime protocol interpretation" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime protocol execution observation" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime protocol invocation result" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime protocol dispatch request" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime protocol adapter selection" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime protocol execution intent" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "recorded runtime operational closure" in attestation.json()["detail"].lower()


def test_runtime_closure_attestation_refuses_when_terminal_settlement_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-settlement-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_terminal_settlement": {
                "executor_identifier": "another-executor",
                "settlement_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    attestation = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert attestation.status_code == 409
    assert "runtime terminal settlement is owned by another executor" in attestation.json()["detail"].lower()


def test_repeated_runtime_closure_attestation_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-closure-attestation-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["attestation_record_id"]
        == second.json()["result"]["attestation_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_publication_contract_records_for_valid_closure_attestation_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 200
    payload = publication.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["publication_contract_family"]
        == "placeholder_runtime_publication_contract"
    )
    assert (
        payload["result"]["publication_contract_payload"]["publication_state"]
        == "placeholder_runtime_publication_contract_ready"
    )
    assert (
        payload["result"]["publication_contract_payload"]["schema_version"]
        == "placeholder-runtime-publication-contract.v1"
    )
    assert (
        payload["result"]["publication_contract_payload"]["publication_classification"]
        == "placeholder_externally_publishable_runtime_finalization_ready"
    )
    assert (
        payload["result"]["publication_contract_payload"]["consumer_scope"]
        == "placeholder_runtime_consumer"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_publication_contract"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_publication_contract"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_publication_contract"]["status"]
        == "recorded"
    )


def test_runtime_publication_contract_refuses_when_closure_attestation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-attestation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime closure attestation" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_terminal_settlement_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-settlement",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_terminal_settlement"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime terminal settlement" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_protocol_reconciliation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-reconciliation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_reconciliation"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime protocol reconciliation" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-interpretation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_interpretation"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime protocol interpretation" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime protocol execution observation" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime protocol invocation result" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime protocol dispatch request" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime protocol adapter selection" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime protocol execution intent" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "recorded runtime operational closure" in publication.json()["detail"].lower()


def test_runtime_publication_contract_refuses_when_closure_attestation_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-attestation-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_closure_attestation": {
                "executor_identifier": "another-executor",
                "attestation_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    publication = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert publication.status_code == 409
    assert "runtime closure attestation is owned by another executor" in publication.json()["detail"].lower()


def test_repeated_runtime_publication_contract_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-publication-contract-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["publication_contract_record_id"]
        == second.json()["result"]["publication_contract_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_externalization_envelope_records_for_valid_publication_contract_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 200
    payload = envelope.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["envelope_family"]
        == "placeholder_runtime_externalization_envelope"
    )
    assert (
        payload["result"]["envelope_payload"]["envelope_state"]
        == "placeholder_externalization_envelope_recorded"
    )
    assert (
        payload["result"]["envelope_payload"]["schema_version"]
        == "placeholder-runtime-externalization-envelope.v1"
    )
    assert (
        payload["result"]["envelope_payload"]["delivery_readiness_classification"]
        == "placeholder_runtime_delivery_readiness_ready"
    )
    assert (
        payload["result"]["envelope_payload"]["target_channel_family"]
        == "placeholder_external_runtime_delivery"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_externalization_envelope"]["status"]
        == "recorded"
    )
    assert (
        meter_command.result_summary["runtime_externalization_envelope"]["status"]
        == "recorded"
    )
    assert (
        job_run.result_summary["runtime_externalization_envelope"]["status"]
        == "recorded"
    )


def test_runtime_externalization_envelope_refuses_when_publication_contract_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-publication",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime publication contract" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_closure_attestation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-attestation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_closure_attestation"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime closure attestation" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_terminal_settlement_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-settlement",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_terminal_settlement"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime terminal settlement" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_protocol_reconciliation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-reconciliation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_reconciliation"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol reconciliation" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-interpretation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_interpretation"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol interpretation" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol execution observation" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol invocation result" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol dispatch request" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol adapter selection" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol execution intent" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime operational closure" in envelope.json()["detail"].lower()


def test_runtime_externalization_envelope_refuses_when_publication_contract_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-publication-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_publication_contract": {
                "executor_identifier": "another-executor",
                "publication_contract_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    envelope = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "runtime publication contract is owned by another executor" in envelope.json()["detail"].lower()


def test_repeated_runtime_externalization_envelope_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-externalization-envelope-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["envelope_record_id"]
        == second.json()["result"]["envelope_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_delivery_contract_records_for_valid_externalization_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 200
    payload = delivery.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["delivery_contract_family"]
        == "placeholder_runtime_delivery_contract"
    )
    assert (
        payload["result"]["delivery_contract_payload"]["delivery_state"]
        == "placeholder_dispatch_readiness_recorded"
    )
    assert (
        payload["result"]["delivery_contract_payload"]["schema_version"]
        == "placeholder-runtime-delivery-contract.v1"
    )
    assert (
        payload["result"]["delivery_contract_payload"]["dispatch_readiness_classification"]
        == "placeholder_runtime_delivery_contract_ready"
    )
    assert (
        payload["result"]["delivery_contract_payload"]["delivery_target_family"]
        == "placeholder_external_delivery_dispatch"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_delivery_contract"]["status"] == "recorded"
    )
    assert meter_command.result_summary["runtime_delivery_contract"]["status"] == "recorded"
    assert job_run.result_summary["runtime_delivery_contract"]["status"] == "recorded"


def test_runtime_delivery_contract_refuses_when_externalization_envelope_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-envelope",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime externalization envelope" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_publication_contract_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-publication",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_publication_contract"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime publication contract" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_closure_attestation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-attestation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_closure_attestation"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime closure attestation" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_terminal_settlement_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-settlement",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_terminal_settlement"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime terminal settlement" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_protocol_reconciliation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-reconciliation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_reconciliation"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime protocol reconciliation" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_protocol_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-interpretation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_interpretation"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime protocol interpretation" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime protocol execution observation" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime protocol invocation result" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime protocol dispatch request" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime protocol adapter selection" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime protocol execution intent" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "recorded runtime operational closure" in delivery.json()["detail"].lower()


def test_runtime_delivery_contract_refuses_when_externalization_envelope_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-envelope-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_externalization_envelope": {
                "executor_identifier": "another-executor",
                "envelope_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    delivery = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert delivery.status_code == 409
    assert "runtime externalization envelope is owned by another executor" in delivery.json()["detail"].lower()


def test_repeated_runtime_delivery_contract_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-delivery-contract-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["delivery_contract_record_id"]
        == second.json()["result"]["delivery_contract_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_dispatch_envelope_records_for_valid_delivery_contract_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-success",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 200
    payload = envelope.json()
    assert payload["result"]["status"] == "recorded"
    assert (
        payload["result"]["dispatch_envelope_family"]
        == "placeholder_runtime_dispatch_envelope"
    )
    assert (
        payload["result"]["dispatch_envelope_payload"]["dispatch_envelope_state"]
        == "placeholder_handoff_readiness_recorded"
    )
    assert (
        payload["result"]["dispatch_envelope_payload"]["schema_version"]
        == "placeholder-runtime-dispatch-envelope.v1"
    )
    assert (
        payload["result"]["dispatch_envelope_payload"]["dispatch_classification"]
        == "placeholder_runtime_dispatch_envelope_ready"
    )
    assert (
        payload["result"]["dispatch_envelope_payload"]["outbound_channel_family"]
        == "placeholder_outbound_delivery_channel"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_dispatch_envelope"]["status"] == "recorded"
    )
    assert meter_command.result_summary["runtime_dispatch_envelope"]["status"] == "recorded"
    assert job_run.result_summary["runtime_dispatch_envelope"]["status"] == "recorded"


def test_runtime_dispatch_envelope_refuses_when_delivery_contract_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-delivery-contract",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime delivery contract" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_externalization_envelope_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-externalization-envelope",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_externalization_envelope"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime externalization envelope" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_publication_contract_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-publication-contract",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_publication_contract"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime publication contract" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_closure_attestation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-closure-attestation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_closure_attestation"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime closure attestation" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_terminal_settlement_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-terminal-settlement",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_terminal_settlement"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime terminal settlement" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_protocol_reconciliation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-reconciliation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_reconciliation"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol reconciliation" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_protocol_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-interpretation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_interpretation"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol interpretation" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-observation",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol execution observation" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-invocation-result",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol invocation result" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-dispatch-request",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol dispatch request" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-selection",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol adapter selection" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-intent",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime protocol execution intent" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-no-closure",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "recorded runtime operational closure" in envelope.json()["detail"].lower()


def test_runtime_dispatch_envelope_refuses_when_delivery_contract_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-owner-mismatch",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_delivery_contract": {
                "executor_identifier": "another-executor",
                "delivery_contract_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    envelope = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert envelope.status_code == 409
    assert "runtime delivery contract is owned by another executor" in envelope.json()["detail"].lower()


def test_repeated_runtime_dispatch_envelope_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _ = _create_started_attempt(
        client,
        db_session,
        token,
        mock_execution={"outcome": "succeeded"},
        command_template_code="runtime-dispatch-envelope-repeat",
        max_retries=0,
    )
    start = _start_runtime_execution_session(client, attempt_id)
    session_identifier = start.json()["result"]["session_identifier"]
    _finalize_runtime_execution_session(client, attempt_id, session_identifier)
    _record_runtime_execution_outcome(client, attempt_id, session_identifier)
    _bridge_runtime_execution_outcome_to_attempt(client, attempt_id, session_identifier)
    _bridge_runtime_attempt_disposition_to_post_processing(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_post_processing_to_follow_up_materialization(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_follow_up_materialization_to_operational_closure(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_operational_closure_to_protocol_execution_intent(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_intent_to_adapter_selection(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_dispatch_request_to_invocation_result(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_invocation_result_to_execution_observation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_execution_observation_to_interpretation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_interpretation_to_reconciliation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_terminal_settlement_to_closure_attestation(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_closure_attestation_to_publication_contract(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_publication_contract_to_externalization_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    _bridge_runtime_externalization_envelope_to_delivery_contract(
        client,
        attempt_id,
        session_identifier,
    )

    first = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )
    second = _bridge_runtime_delivery_contract_to_dispatch_envelope(
        client,
        attempt_id,
        session_identifier,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["dispatch_envelope_record_id"]
        == second.json()["result"]["dispatch_envelope_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_relay_control_adapter_executes_for_valid_disconnect_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-success",
        category=CommandCategory.REMOTE_DISCONNECT,
    )

    response = _execute_runtime_relay_control_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["adapter_key"] == "gurux-dlms-bridge"
    assert payload["result"]["protocol_family"] == "dlms_cosem"
    assert payload["result"]["relay_operation"] == "disconnect"
    assert payload["result"]["command_category"] == "remote_disconnect"
    assert payload["result"]["adapter_acknowledgment_state"] == "accepted"
    assert payload["result"]["protocol_stage_outcome"] == "relay_operation_completed"
    assert payload["result"]["execution_outcome"] == "succeeded"
    assert payload["result"]["adapter_result_summary"]["gurux_operation"]["method_name"] == "remote_disconnect"
    assert payload["result"]["adapter_result_summary"]["gurux_operation"]["method_index"] == 1
    assert (
        payload["result"]["adapter_result_summary"]["gurux_invocation_stub"]["transport_adapter"]
        == "gurux_stub"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_invocation_stub"]["request_shape"]["method_name"]
        == "remote_disconnect"
    )
    assert (
        payload["result"]["adapter_response_snapshot"]["gurux_invocation_request"]["operation"]["method_name"]
        == "remote_disconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_interpreter"]["invocation_status"]
        == "acknowledged"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_interpreter"]["execution_outcome"]
        == "succeeded"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_resolved_transport_profile"]["gurux_operation"]["method_name"]
        == "remote_disconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_resolved_transport_profile"]["transport_profile"]["transport_type"]
        == "tcp_ip"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_validated_target"]["gurux_operation"]["method_name"]
        == "remote_disconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_validated_target"]["transport_prerequisites_present"]
        is True
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_normalized_request"]["gurux_operation"]["method_name"]
        == "remote_disconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_normalized_request"]["invocation_context"]["relay_operation"]
        == "disconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["relay_operation"]
        == "disconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["resolved_transport_profile_present"]
        is True
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["resolved_protocol_profile_id"]
        == payload["result"]["adapter_result_summary"]["gurux_resolved_transport_profile"]["protocol_profile"]["protocol_profile_id"]
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["stopped_at_stage"]
        is None
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["terminal_execution_outcome"]
        == "succeeded"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_phase_progression"]["resolver_stage_state"]
        == "resolved"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_phase_progression"]["validator_stage_state"]
        == "validated"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_phase_progression"]["normalizer_stage_state"]
        == "normalized"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_phase_progression"]["invocation_stage_state"]
        == "acknowledged"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_phase_progression"]["interpreter_stage_state"]
        == "accepted"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_terminal_adapter_status"]["adapter_terminal_state"]
        == "acknowledged"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_terminal_adapter_status"]["terminal_acknowledgment_class"]
        == "accepted"
    )

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert (
        attempt.execution_metadata["runtime_relay_control_execution"]["status"]
        == "completed"
    )
    assert (
        meter_command.result_summary["runtime_relay_control_execution"]["status"]
        == "completed"
    )
    assert (
        job_run.result_summary["runtime_relay_control_execution"]["status"]
        == "completed"
    )


def test_runtime_relay_control_adapter_refuses_for_non_relay_command_category(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-non-relay",
        category=CommandCategory.ON_DEMAND_READ,
    )

    response = _execute_runtime_relay_control_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 409
    assert "disconnect and reconnect commands" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_executes_for_valid_reconnect_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-reconnect-success",
        category=CommandCategory.REMOTE_RECONNECT,
    )

    response = _execute_runtime_relay_control_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["relay_operation"] == "reconnect"
    assert payload["result"]["command_category"] == "remote_reconnect"
    assert payload["result"]["adapter_result_summary"]["gurux_operation"]["method_name"] == "remote_reconnect"
    assert payload["result"]["adapter_result_summary"]["gurux_operation"]["method_index"] == 2
    assert (
        payload["result"]["adapter_result_summary"]["gurux_invocation_stub"]["invocation_status"]
        == "acknowledged"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_invocation_stub"]["request_shape"]["method_name"]
        == "remote_reconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_interpreter"]["protocol_stage_outcome"]
        == "relay_operation_completed"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_resolved_transport_profile"]["gurux_operation"]["method_name"]
        == "remote_reconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_resolved_transport_profile"]["transport_profile"]["transport_locator"]
        == payload["result"]["adapter_response_snapshot"]["gurux_invocation_request"]["transport_locator"]
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_validated_target"]["gurux_operation"]["method_name"]
        == "remote_reconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_validated_target"]["security_prerequisites_present"]
        is True
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_normalized_request"]["gurux_operation"]["method_name"]
        == "remote_reconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_normalized_request"]["invocation_context"]["relay_operation"]
        == "reconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["relay_operation"]
        == "reconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["resolved_transport_profile_present"]
        is True
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_audit_summary"]["terminal_invocation_status"]
        == "acknowledged"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_phase_progression"]["relay_operation"]
        == "reconnect"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_execution_phase_progression"]["stopped_at_stage"]
        is None
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_terminal_adapter_status"]["adapter_terminal_state"]
        == "acknowledged"
    )


def test_runtime_relay_control_adapter_refuses_when_gurux_mapper_feature_is_disabled(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-feature-disabled",
    )
    monkeypatch.setattr(settings, "enable_runtime_relay_control_gurux_mapper", False)

    response = _execute_runtime_relay_control_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 409
    assert "gurux mapper is disabled" in response.json()["detail"].lower()


def test_runtime_relay_control_gurux_mapper_refuses_unsupported_operation() -> None:
    with pytest.raises(ValueError, match="Unsupported relay operation"):
        _map_relay_control_operation_to_gurux_definition("unsupported")


def test_runtime_relay_control_gurux_transport_profile_resolver_refuses_missing_endpoint_code() -> None:
    with pytest.raises(
        ValueError,
        match="Missing adapter prerequisites for the relay-control Gurux transport/profile resolver",
    ):
        _resolve_gurux_relay_control_transport_profile(
            RuntimeRelayControlAdapterRequest(
                adapter_key="gurux-dlms-bridge",
                protocol_family=ProtocolFamily.DLMS_COSEM,
                operation=RuntimeRelayControlOperation.DISCONNECT,
                command_category=CommandCategory.REMOTE_DISCONNECT,
                execution_context=RuntimeExecutionContext(
                    command_id=uuid.uuid4(),
                    job_run_id=uuid.uuid4(),
                    command_attempt_id=uuid.uuid4(),
                    correlation_id="corr-1",
                    worker_identifier="worker-runtime-1",
                    request_id="req-1",
                    triggered_at=datetime.now(UTC),
                ),
                target=MeterRuntimeTarget(
                    meter_id=uuid.uuid4(),
                    serial_number="meter-001",
                    manufacturer_code="GURUX",
                    meter_model_code="DLMS-1",
                    meter_model_name="DLMS Test",
                    endpoint_assignment_id=uuid.uuid4(),
                    endpoint_id=uuid.uuid4(),
                    endpoint_code="",
                    protocol_association_profile_id=uuid.uuid4(),
                ),
                transport=RuntimeTransportConfig(
                    endpoint_transport_type=ConnectivityTransportType.TCP_IP,
                    host="127.0.0.1",
                    port=4059,
                ),
                security=RuntimeSecurityMaterialRefs(
                    authentication_mode=AssociationAuthenticationMode.LOW,
                    password_secret_ref="secret://relay/password",
                ),
                dispatch_envelope_record_id="dispatch-envelope-1",
                trace_references={"session_identifier": "session-1"},
                lineage=RuntimeExecutionSessionLineage(
                    dispatch_request_identity="dispatch-identity-1",
                    queue_message_id="queue-message-1",
                    claim_token="claim-token-1",
                    intended_worker_path="runtime-relay-control",
                ),
            ),
            _map_relay_control_operation_to_gurux_definition(
                RuntimeRelayControlOperation.DISCONNECT
            ),
        )


def test_runtime_relay_control_gurux_target_validator_refuses_missing_serial_number() -> None:
    request = RuntimeRelayControlAdapterRequest(
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        operation=RuntimeRelayControlOperation.DISCONNECT,
        command_category=CommandCategory.REMOTE_DISCONNECT,
        execution_context=RuntimeExecutionContext(
            command_id=uuid.uuid4(),
            job_run_id=uuid.uuid4(),
            command_attempt_id=uuid.uuid4(),
            correlation_id="corr-1",
            worker_identifier="worker-runtime-1",
            request_id="req-1",
            triggered_at=datetime.now(UTC),
        ),
        target=MeterRuntimeTarget(
            meter_id=uuid.uuid4(),
            serial_number="",
            manufacturer_code="GURUX",
            meter_model_code="DLMS-1",
            meter_model_name="DLMS Test",
            endpoint_assignment_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            endpoint_code="endpoint-001",
            protocol_association_profile_id=uuid.uuid4(),
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=ConnectivityTransportType.TCP_IP,
            host="127.0.0.1",
            port=4059,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=AssociationAuthenticationMode.LOW,
            password_secret_ref="secret://relay/password",
        ),
        dispatch_envelope_record_id="dispatch-envelope-1",
        trace_references={"session_identifier": "session-1"},
        lineage=RuntimeExecutionSessionLineage(
            dispatch_request_identity="dispatch-identity-1",
            queue_message_id="queue-message-1",
            claim_token="claim-token-1",
            intended_worker_path="runtime-relay-control",
        ),
    )
    with pytest.raises(
        ValueError,
        match="Missing adapter prerequisites for the relay-control Gurux target-object validator",
    ):
        _validate_gurux_relay_control_target_object(
            request,
            _resolve_gurux_relay_control_transport_profile(
                request,
                _map_relay_control_operation_to_gurux_definition(
                    RuntimeRelayControlOperation.DISCONNECT
                ),
            ),
        )


def test_runtime_relay_control_gurux_normalizer_refuses_missing_transport_locator() -> None:
    valid_request = RuntimeRelayControlAdapterRequest(
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        operation=RuntimeRelayControlOperation.DISCONNECT,
        command_category=CommandCategory.REMOTE_DISCONNECT,
        execution_context=RuntimeExecutionContext(
            command_id=uuid.uuid4(),
            job_run_id=uuid.uuid4(),
            command_attempt_id=uuid.uuid4(),
            correlation_id="corr-1",
            worker_identifier="worker-runtime-1",
            request_id="req-1",
            triggered_at=datetime.now(UTC),
        ),
        target=MeterRuntimeTarget(
            meter_id=uuid.uuid4(),
            serial_number="meter-001",
            manufacturer_code="GURUX",
            meter_model_code="DLMS-1",
            meter_model_name="DLMS Test",
            endpoint_assignment_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            endpoint_code="endpoint-001",
            protocol_association_profile_id=uuid.uuid4(),
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=ConnectivityTransportType.TCP_IP,
            host="127.0.0.1",
            port=4059,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=AssociationAuthenticationMode.LOW,
            password_secret_ref="secret://relay/password",
        ),
        dispatch_envelope_record_id="dispatch-envelope-1",
        trace_references={"session_identifier": "session-1"},
        lineage=RuntimeExecutionSessionLineage(
            dispatch_request_identity="dispatch-identity-1",
            queue_message_id="queue-message-1",
            claim_token="claim-token-1",
            intended_worker_path="runtime-relay-control",
        ),
    )
    with pytest.raises(
        ValueError,
        match="Missing adapter prerequisites for the relay-control Gurux request normalizer",
    ):
        _normalize_gurux_relay_control_request(
            RuntimeRelayControlAdapterRequest(
                adapter_key="gurux-dlms-bridge",
                protocol_family=ProtocolFamily.DLMS_COSEM,
                operation=RuntimeRelayControlOperation.DISCONNECT,
                command_category=CommandCategory.REMOTE_DISCONNECT,
                execution_context=RuntimeExecutionContext(
                    command_id=uuid.uuid4(),
                    job_run_id=uuid.uuid4(),
                    command_attempt_id=uuid.uuid4(),
                    correlation_id="corr-1",
                    worker_identifier="worker-runtime-1",
                    request_id="req-1",
                    triggered_at=datetime.now(UTC),
                ),
                target=MeterRuntimeTarget(
                    meter_id=uuid.uuid4(),
                    serial_number="meter-001",
                    manufacturer_code="GURUX",
                    meter_model_code="DLMS-1",
                    meter_model_name="DLMS Test",
                    endpoint_assignment_id=uuid.uuid4(),
                    endpoint_id=uuid.uuid4(),
                    endpoint_code="endpoint-001",
                    protocol_association_profile_id=uuid.uuid4(),
                ),
                transport=RuntimeTransportConfig(
                    endpoint_transport_type=ConnectivityTransportType.TCP_IP,
                    port=4059,
                ),
                security=RuntimeSecurityMaterialRefs(
                    authentication_mode=AssociationAuthenticationMode.LOW,
                    password_secret_ref="secret://relay/password",
                ),
                dispatch_envelope_record_id="dispatch-envelope-1",
                trace_references={"session_identifier": "session-1"},
                lineage=RuntimeExecutionSessionLineage(
                    dispatch_request_identity="dispatch-identity-1",
                    queue_message_id="queue-message-1",
                    claim_token="claim-token-1",
                    intended_worker_path="runtime-relay-control",
                ),
            ),
            _resolve_gurux_relay_control_transport_profile(
                valid_request,
                _map_relay_control_operation_to_gurux_definition(
                    RuntimeRelayControlOperation.DISCONNECT
                ),
            ).model_copy(
                update={
                    "transport_profile": {
                        "transport_type": "tcp_ip",
                        "transport_locator": "",
                        "port": 4059,
                    }
                }
            ),
            _validate_gurux_relay_control_target_object(
                valid_request,
                _resolve_gurux_relay_control_transport_profile(
                    valid_request,
                    _map_relay_control_operation_to_gurux_definition(
                        RuntimeRelayControlOperation.DISCONNECT
                    ),
                ),
            ),
        )


def test_runtime_relay_control_gurux_execution_audit_summary_handles_partial_stages() -> None:
    request = RuntimeRelayControlAdapterRequest(
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        operation=RuntimeRelayControlOperation.DISCONNECT,
        command_category=CommandCategory.REMOTE_DISCONNECT,
        execution_context=RuntimeExecutionContext(
            command_id=uuid.uuid4(),
            job_run_id=uuid.uuid4(),
            command_attempt_id=uuid.uuid4(),
            correlation_id="corr-1",
            worker_identifier="worker-runtime-1",
            request_id="req-1",
            triggered_at=datetime.now(UTC),
        ),
        target=MeterRuntimeTarget(
            meter_id=uuid.uuid4(),
            serial_number="meter-001",
            manufacturer_code="GURUX",
            meter_model_code="DLMS-1",
            meter_model_name="DLMS Test",
            endpoint_assignment_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            endpoint_code="endpoint-001",
            protocol_association_profile_id=uuid.uuid4(),
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=ConnectivityTransportType.TCP_IP,
            host="127.0.0.1",
            port=4059,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=AssociationAuthenticationMode.LOW,
            password_secret_ref="secret://relay/password",
        ),
        dispatch_envelope_record_id="dispatch-envelope-1",
        trace_references={"session_identifier": "session-1"},
        lineage=RuntimeExecutionSessionLineage(
            dispatch_request_identity="dispatch-identity-1",
            queue_message_id="queue-message-1",
            claim_token="claim-token-1",
            intended_worker_path="runtime-relay-control",
        ),
    )
    operation = _map_relay_control_operation_to_gurux_definition(
        RuntimeRelayControlOperation.DISCONNECT
    )
    resolved_transport_profile = _resolve_gurux_relay_control_transport_profile(
        request,
        operation,
    )
    validated_target = _validate_gurux_relay_control_target_object(
        request,
        resolved_transport_profile,
    )
    normalized_request = _normalize_gurux_relay_control_request(
        request,
        resolved_transport_profile,
        validated_target,
    )
    invocation_response = GuruxRelayControlInvocationStubResponse(
        transport_adapter="gurux_stub",
        invocation_status="acknowledged",
        acknowledged=True,
        invocation_reference="gurux-relay-invocation:test:remote_disconnect",
        request_shape={"method_name": "remote_disconnect"},
        response_shape={"invocation_status": "acknowledged"},
    )
    interpreted_result = _interpret_gurux_relay_control_stub_response(
        invocation_response,
        requested_outcome=RuntimeCommandOutcome.SUCCEEDED,
        error_detail=None,
    )

    validation_stop = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
    )
    resolution_stop = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=None,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
    )
    normalization_stop = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
    )
    invocation_stop = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=None,
        interpreted_result=None,
    )
    interpretation_stop = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=None,
    )
    complete = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=interpreted_result,
    )

    assert resolution_stop.stopped_at_stage == "resolution"
    assert validation_stop.stopped_at_stage == "validation"
    assert normalization_stop.stopped_at_stage == "normalization"
    assert invocation_stop.stopped_at_stage == "invocation"
    assert interpretation_stop.stopped_at_stage == "interpretation"
    assert complete.stopped_at_stage is None
    assert complete.terminal_execution_outcome == RuntimeCommandOutcome.SUCCEEDED


def test_runtime_relay_control_gurux_execution_phase_progression_handles_partial_stages() -> None:
    request = RuntimeRelayControlAdapterRequest(
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        operation=RuntimeRelayControlOperation.DISCONNECT,
        command_category=CommandCategory.REMOTE_DISCONNECT,
        execution_context=RuntimeExecutionContext(
            command_id=uuid.uuid4(),
            job_run_id=uuid.uuid4(),
            command_attempt_id=uuid.uuid4(),
            correlation_id="corr-1",
            worker_identifier="worker-runtime-1",
            request_id="req-1",
            triggered_at=datetime.now(UTC),
        ),
        target=MeterRuntimeTarget(
            meter_id=uuid.uuid4(),
            serial_number="meter-001",
            manufacturer_code="GURUX",
            meter_model_code="DLMS-1",
            meter_model_name="DLMS Test",
            endpoint_assignment_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            endpoint_code="endpoint-001",
            protocol_association_profile_id=uuid.uuid4(),
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=ConnectivityTransportType.TCP_IP,
            host="127.0.0.1",
            port=4059,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=AssociationAuthenticationMode.LOW,
            password_secret_ref="secret://relay/password",
        ),
        dispatch_envelope_record_id="dispatch-envelope-1",
        trace_references={"session_identifier": "session-1"},
        lineage=RuntimeExecutionSessionLineage(
            dispatch_request_identity="dispatch-identity-1",
            queue_message_id="queue-message-1",
            claim_token="claim-token-1",
            intended_worker_path="runtime-relay-control",
        ),
    )
    operation = _map_relay_control_operation_to_gurux_definition(
        RuntimeRelayControlOperation.DISCONNECT
    )
    resolved_transport_profile = _resolve_gurux_relay_control_transport_profile(
        request,
        operation,
    )
    validated_target = _validate_gurux_relay_control_target_object(
        request,
        resolved_transport_profile,
    )
    normalized_request = _normalize_gurux_relay_control_request(
        request,
        resolved_transport_profile,
        validated_target,
    )
    invocation_response = GuruxRelayControlInvocationStubResponse(
        transport_adapter="gurux_stub",
        invocation_status="acknowledged",
        acknowledged=True,
        invocation_reference="gurux-relay-invocation:test:remote_disconnect",
        request_shape={"method_name": "remote_disconnect"},
        response_shape={"invocation_status": "acknowledged"},
    )
    interpreted_result = _interpret_gurux_relay_control_stub_response(
        invocation_response,
        requested_outcome=RuntimeCommandOutcome.SUCCEEDED,
        error_detail=None,
    )

    resolution_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=None,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
    )
    validation_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
    )
    complete_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=interpreted_result,
    )

    resolution_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=None,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
        execution_audit_summary=resolution_audit,
    )
    validation_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
        execution_audit_summary=validation_audit,
    )
    complete_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=interpreted_result,
        execution_audit_summary=complete_audit,
    )

    assert resolution_progression.resolver_stage_state == "failed"
    assert resolution_progression.validator_stage_state == "not_started"
    assert resolution_progression.stopped_at_stage == "resolution"
    assert validation_progression.resolver_stage_state == "resolved"
    assert validation_progression.validator_stage_state == "failed"
    assert validation_progression.normalizer_stage_state == "not_started"
    assert validation_progression.stopped_at_stage == "validation"
    assert complete_progression.resolver_stage_state == "resolved"
    assert complete_progression.validator_stage_state == "validated"
    assert complete_progression.normalizer_stage_state == "normalized"
    assert complete_progression.invocation_stage_state == "acknowledged"
    assert complete_progression.interpreter_stage_state == "accepted"
    assert complete_progression.terminal_execution_outcome == RuntimeCommandOutcome.SUCCEEDED


def test_runtime_relay_control_gurux_terminal_adapter_status_handles_partial_stages() -> None:
    request = RuntimeRelayControlAdapterRequest(
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        operation=RuntimeRelayControlOperation.DISCONNECT,
        command_category=CommandCategory.REMOTE_DISCONNECT,
        execution_context=RuntimeExecutionContext(
            command_id=uuid.uuid4(),
            job_run_id=uuid.uuid4(),
            command_attempt_id=uuid.uuid4(),
            correlation_id="corr-1",
            worker_identifier="worker-runtime-1",
            request_id="req-1",
            triggered_at=datetime.now(UTC),
        ),
        target=MeterRuntimeTarget(
            meter_id=uuid.uuid4(),
            serial_number="meter-001",
            manufacturer_code="GURUX",
            meter_model_code="DLMS-1",
            meter_model_name="DLMS Test",
            endpoint_assignment_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            endpoint_code="endpoint-001",
            protocol_association_profile_id=uuid.uuid4(),
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=ConnectivityTransportType.TCP_IP,
            host="127.0.0.1",
            port=4059,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=AssociationAuthenticationMode.LOW,
            password_secret_ref="secret://relay/password",
        ),
        dispatch_envelope_record_id="dispatch-envelope-1",
        trace_references={"session_identifier": "session-1"},
        lineage=RuntimeExecutionSessionLineage(
            dispatch_request_identity="dispatch-identity-1",
            queue_message_id="queue-message-1",
            claim_token="claim-token-1",
            intended_worker_path="runtime-relay-control",
        ),
    )
    operation = _map_relay_control_operation_to_gurux_definition(
        RuntimeRelayControlOperation.DISCONNECT
    )
    resolved_transport_profile = _resolve_gurux_relay_control_transport_profile(
        request,
        operation,
    )
    validated_target = _validate_gurux_relay_control_target_object(
        request,
        resolved_transport_profile,
    )
    normalized_request = _normalize_gurux_relay_control_request(
        request,
        resolved_transport_profile,
        validated_target,
    )
    invocation_response = GuruxRelayControlInvocationStubResponse(
        transport_adapter="gurux_stub",
        invocation_status="acknowledged",
        acknowledged=True,
        invocation_reference="gurux-relay-invocation:test:remote_disconnect",
        request_shape={"method_name": "remote_disconnect"},
        response_shape={"invocation_status": "acknowledged"},
    )
    interpreted_result = _interpret_gurux_relay_control_stub_response(
        invocation_response,
        requested_outcome=RuntimeCommandOutcome.SUCCEEDED,
        error_detail=None,
    )

    resolution_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=None,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
    )
    resolution_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=None,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
        execution_audit_summary=resolution_audit,
    )
    validation_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
    )
    validation_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=None,
        normalized_request=None,
        invocation_response=None,
        interpreted_result=None,
        execution_audit_summary=validation_audit,
    )
    invocation_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=None,
        interpreted_result=None,
    )
    invocation_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=None,
        interpreted_result=None,
        execution_audit_summary=invocation_audit,
    )
    interpretation_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=None,
    )
    interpretation_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=None,
        execution_audit_summary=interpretation_audit,
    )
    complete_audit = _build_gurux_relay_control_execution_audit_summary(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=interpreted_result,
    )
    complete_progression = _project_gurux_relay_control_execution_phase_state(
        request=request,
        gurux_operation=operation,
        resolved_transport_profile=resolved_transport_profile,
        validated_target=validated_target,
        normalized_request=normalized_request,
        invocation_response=invocation_response,
        interpreted_result=interpreted_result,
        execution_audit_summary=complete_audit,
    )

    resolution_status = _project_gurux_relay_control_terminal_adapter_status(
        request=request,
        execution_phase_progression=resolution_progression,
        execution_audit_summary=resolution_audit,
        interpreted_result=None,
    )
    validation_status = _project_gurux_relay_control_terminal_adapter_status(
        request=request,
        execution_phase_progression=validation_progression,
        execution_audit_summary=validation_audit,
        interpreted_result=None,
    )
    invocation_status = _project_gurux_relay_control_terminal_adapter_status(
        request=request,
        execution_phase_progression=invocation_progression,
        execution_audit_summary=invocation_audit,
        interpreted_result=None,
    )
    interpretation_status = _project_gurux_relay_control_terminal_adapter_status(
        request=request,
        execution_phase_progression=interpretation_progression,
        execution_audit_summary=interpretation_audit,
        interpreted_result=None,
    )
    complete_status = _project_gurux_relay_control_terminal_adapter_status(
        request=request,
        execution_phase_progression=complete_progression,
        execution_audit_summary=complete_audit,
        interpreted_result=interpreted_result,
    )

    assert resolution_status.adapter_terminal_state == "blocked_pre_invocation"
    assert validation_status.adapter_terminal_state == "blocked_pre_invocation"
    assert invocation_status.adapter_terminal_state == "unavailable"
    assert interpretation_status.adapter_terminal_state == "unusable_response"
    assert complete_status.adapter_terminal_state == "acknowledged"
    assert complete_status.terminal_acknowledgment_class == "accepted"
    assert complete_status.final_execution_disposition == RuntimeCommandOutcome.SUCCEEDED


def test_runtime_relay_control_adapter_interprets_rejected_stub_outcome(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-rejected-interpretation",
        mock_execution={
            "outcome": "succeeded",
            "invocation_status": "rejected",
            "adapter_acknowledged": False,
            "error_detail": "Relay operation rejected by Gurux stub path.",
        },
    )

    response = _execute_runtime_relay_control_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["adapter_acknowledgment_state"] == "rejected"
    assert payload["result"]["protocol_stage_outcome"] == "relay_operation_failed"
    assert payload["result"]["execution_outcome"] == "failed"
    assert payload["result"]["error_category"] == "adapter_rejected"
    assert (
        payload["result"]["adapter_result_summary"]["gurux_terminal_adapter_status"]["adapter_terminal_state"]
        == "rejected"
    )
    assert (
        payload["result"]["adapter_result_summary"]["gurux_interpreter"]["interpreter_summary"]
        .lower()
        .startswith("gurux relay-control invocation was explicitly rejected")
    )


def test_runtime_relay_control_adapter_refuses_unusable_gurux_interpreter_response(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-invalid-interpreter-response",
        mock_execution={
            "outcome": "succeeded",
            "invocation_status": "invalid_response",
        },
    )

    response = _execute_runtime_relay_control_adapter(
        client,
        attempt_id,
        session_identifier,
    )

    assert response.status_code == 409
    assert "unusable gurux relay-control invocation stub response" in response.json()[
        "detail"
    ].lower()


def test_runtime_relay_control_gurux_interpreter_refuses_unusable_response_shape() -> None:
    with pytest.raises(ValueError, match="Unusable Gurux relay-control invocation stub response"):
        _interpret_gurux_relay_control_stub_response(
            GuruxRelayControlInvocationStubResponse(
                transport_adapter="gurux_stub",
                invocation_status="invalid_response",
                acknowledged=False,
                invocation_reference="gurux-relay-invocation:test:remote_disconnect",
                request_shape={"method_name": "remote_disconnect"},
                response_shape={"invocation_status": "invalid_response"},
            ),
            requested_outcome=RuntimeCommandOutcome.SUCCEEDED,
            error_detail=None,
        )


def test_runtime_relay_control_adapter_refuses_when_dispatch_envelope_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-dispatch-envelope",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_dispatch_envelope"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime dispatch envelope" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_delivery_contract_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-delivery-contract",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_delivery_contract"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime delivery contract" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_externalization_envelope_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-externalization-envelope",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_externalization_envelope"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime externalization envelope" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_publication_contract_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-publication-contract",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_publication_contract"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime publication contract" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_closure_attestation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-closure-attestation",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_closure_attestation"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime closure attestation" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_terminal_settlement_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-terminal-settlement",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_terminal_settlement"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime terminal settlement" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_protocol_reconciliation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-reconciliation",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_reconciliation"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime protocol reconciliation" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_protocol_interpretation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-interpretation",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_interpretation"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime protocol interpretation" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_execution_observation_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-observation",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_observation"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime protocol execution observation" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_invocation_result_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-invocation-result",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_invocation_result"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime protocol invocation result" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_dispatch_request_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-dispatch-request",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_dispatch_request"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime protocol dispatch request" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_adapter_selection_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-selection",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_adapter_selection"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime protocol adapter selection" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_protocol_execution_intent_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-intent",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_protocol_execution_intent"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime protocol execution intent" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_operational_closure_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-no-closure",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_operational_closure"},
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime operational closure" in response.json()["detail"].lower()


def test_runtime_relay_control_adapter_refuses_when_dispatch_envelope_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-owner-mismatch",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        section_updates={
            "runtime_dispatch_envelope": {
                "executor_identifier": "another-executor",
                "dispatch_envelope_recorded_by_executor_identifier": "another-executor",
            }
        },
    )

    response = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "runtime dispatch envelope is owned by another executor" in response.json()["detail"].lower()


def test_repeated_runtime_relay_control_adapter_execution_is_idempotent(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-relay-control-repeat",
        category=CommandCategory.REMOTE_RECONNECT,
    )

    first = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)
    second = _execute_runtime_relay_control_adapter(client, attempt_id, session_identifier)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["relay_control_execution_record_id"]
        == second.json()["result"]["relay_control_execution_record_id"]
    )
    assert second.json()["result"]["already_recorded"] is True
