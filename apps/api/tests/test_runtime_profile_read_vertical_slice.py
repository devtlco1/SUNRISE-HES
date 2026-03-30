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
    _build_gurux_capture_load_profile_invocation_request,
    _interpret_gurux_capture_load_profile_response,
    _map_profile_read_operation_to_gurux_definition,
    _normalize_gurux_capture_load_profile_request,
    _validate_gurux_capture_load_profile_target,
    GuruxProfileReadInvocationResponse,
)
from app.runtime.contracts import (
    MeterRuntimeTarget,
    RuntimeCaptureLoadProfileExecutionCategory,
    RuntimeCommandOutcome,
    RuntimeExecutionContext,
    RuntimeExecutionSessionLineage,
    RuntimeProfileReadAdapterRequest,
    RuntimeProfileReadExecutionResult,
    RuntimeProfileReadExecutionStatus,
    RuntimeProfileReadOperation,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from app.runtime.services.runtime_profile_read import (
    _load_runtime_capture_load_profile_execution_digest,
    _load_runtime_capture_load_profile_terminal_status,
    _project_capture_load_profile_execution_digest,
    _project_capture_load_profile_terminal_status,
)
from tests.test_runtime_execution_session_heartbeat_foundation import (
    _persist_attempt_execution_metadata_sections,
    _prepare_runtime_relay_control_chain,
    _set_command_category,
)
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def _execute_runtime_profile_read_adapter(
    client,
    attempt_id: str,
    session_identifier: str,
):
    return client.post(
        f"/api/v1/internal/command-attempts/{attempt_id}/execute-profile-read-adapter",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "executor_identifier": "worker-runtime-1",
            "session_identifier": session_identifier,
        },
    )


def _prepare_runtime_profile_read_chain(
    client,
    db_session: Session,
    token: str,
    *,
    command_template_code: str,
    mock_execution: dict[str, object] | None = None,
) -> tuple[str, str, str, str]:
    if mock_execution is None:
        interval_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        interval_end = interval_start + timedelta(minutes=15)
        mock_execution = {
            "outcome": "succeeded",
            "reading_batch": {
                "source_type": "command_result",
                "captured_at": interval_start.isoformat(),
                "received_at": interval_end.isoformat(),
                "status": "received",
                "load_profile_intervals": [
                    {
                        "channel_id": "00000000-0000-0000-0000-000000000123",
                        "interval_start": interval_start.isoformat(),
                        "interval_end": interval_end.isoformat(),
                        "value_numeric": "11.5",
                        "quality": "good",
                    }
                ],
            },
        }
    return _prepare_runtime_relay_control_chain(
        client,
        db_session,
        token,
        command_template_code=command_template_code,
        category=CommandCategory.PROFILE_CAPTURE,
        mock_execution=mock_execution,
    )


def _build_profile_read_adapter_request_for_tests(
    *,
    reading_batch: dict[str, object] | None = None,
) -> RuntimeProfileReadAdapterRequest:
    now = datetime.now(UTC).replace(microsecond=0)
    interval_end = now + timedelta(minutes=15)
    return RuntimeProfileReadAdapterRequest(
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        operation=RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE,
        command_category=CommandCategory.PROFILE_CAPTURE,
        execution_context=RuntimeExecutionContext(
            command_id=uuid.uuid4(),
            job_run_id=uuid.uuid4(),
            command_attempt_id=uuid.uuid4(),
            correlation_id="corr-profile-1",
            worker_identifier="worker-runtime-1",
            request_id="request-profile-1",
            triggered_at=now,
        ),
        target=MeterRuntimeTarget(
            meter_id=uuid.uuid4(),
            serial_number="SN-PROFILE-1",
            manufacturer_code="ACME",
            meter_model_code="MODEL-1",
            meter_model_name="Model 1",
            endpoint_assignment_id=uuid.uuid4(),
            endpoint_id=uuid.uuid4(),
            endpoint_code="endpoint-profile-1",
            protocol_association_profile_id=uuid.uuid4(),
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=ConnectivityTransportType.TCP_IP,
            host="10.10.10.10",
            port=4059,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=AssociationAuthenticationMode.LOW,
            password_secret_ref="secret://profile/password",
        ),
        request_payload={
            "mock_execution": {
                "reading_batch": reading_batch
                or {
                    "source_type": "command_result",
                    "captured_at": now.isoformat(),
                    "received_at": interval_end.isoformat(),
                    "status": "received",
                    "load_profile_intervals": [
                        {
                            "channel_id": "00000000-0000-0000-0000-000000000123",
                            "interval_start": now.isoformat(),
                            "interval_end": interval_end.isoformat(),
                            "value_numeric": "7.5",
                            "quality": "good",
                        }
                    ],
                }
            }
        },
        normalized_payload=None,
        dispatch_envelope_record_id="dispatch-envelope-profile-1",
        trace_references={"session_identifier": "session-profile-1"},
        lineage=RuntimeExecutionSessionLineage(
            dispatch_request_identity="dispatch-identity-profile-1",
            queue_message_id="queue-message-profile-1",
            claim_token="claim-token-profile-1",
            intended_worker_path="runtime-profile-read",
        ),
    )


def test_runtime_profile_read_adapter_executes_for_valid_profile_chain(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, job_run_id, session_identifier = _prepare_runtime_profile_read_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-profile-read-success",
    )

    response = _execute_runtime_profile_read_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["profile_read_operation"] == "capture_load_profile"
    assert payload["result"]["adapter_result_summary"]["gurux_profile_read_operation"]["obis_code"] == "1.0.99.1.0.255"
    assert payload["result"]["capture_load_profile_execution_digest"]["final_execution_category"] == "completed"
    assert payload["result"]["capture_load_profile_execution_digest"]["load_profile_interval_count"] == 1
    assert payload["result"]["capture_load_profile_terminal_status"]["terminal_status"] == "acknowledged"

    attempt = db_session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))
    meter_command = db_session.get(MeterCommand, uuid.UUID(command_id))
    job_run = db_session.get(JobRun, uuid.UUID(job_run_id))
    assert attempt is not None
    assert meter_command is not None
    assert job_run is not None
    assert attempt.execution_metadata["runtime_profile_read_execution"]["status"] == "completed"
    loaded_digest = _load_runtime_capture_load_profile_execution_digest(
        attempt.execution_metadata
    )
    loaded_terminal_status = _load_runtime_capture_load_profile_terminal_status(
        attempt.execution_metadata
    )
    assert loaded_digest is not None
    assert loaded_terminal_status is not None
    assert loaded_digest.final_execution_category.value == "completed"
    assert loaded_terminal_status.terminal_status.value == "acknowledged"
    assert (
        attempt.execution_metadata["runtime_capture_load_profile_execution_digest"]["final_execution_category"]
        == "completed"
    )
    assert (
        attempt.execution_metadata["runtime_capture_load_profile_terminal_status"]["terminal_status"]
        == "acknowledged"
    )
    assert (
        meter_command.result_summary["runtime_capture_load_profile_execution_digest"]["load_profile_interval_count"]
        == 1
    )
    assert (
        job_run.result_summary["runtime_capture_load_profile_execution_digest"]["channel_count"]
        == 1
    )


def test_runtime_profile_read_adapter_refuses_for_non_profile_command_category(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, command_id, _, session_identifier = _prepare_runtime_profile_read_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-profile-read-non-profile",
        mock_execution={"outcome": "succeeded"},
    )
    _set_command_category(
        db_session,
        command_id=command_id,
        category=CommandCategory.ON_DEMAND_READ,
    )

    response = _execute_runtime_profile_read_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "read-profile commands" in response.json()["detail"].lower()


def test_runtime_profile_read_adapter_refuses_when_dispatch_envelope_is_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_profile_read_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-profile-read-no-dispatch-envelope",
    )
    _persist_attempt_execution_metadata_sections(
        db_session,
        attempt_id,
        removed_sections={"runtime_dispatch_envelope"},
    )

    response = _execute_runtime_profile_read_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "recorded runtime dispatch envelope" in response.json()["detail"].lower()


def test_runtime_profile_read_adapter_refuses_when_dispatch_envelope_belongs_to_another_executor(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_profile_read_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-profile-read-owner-mismatch",
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

    response = _execute_runtime_profile_read_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "runtime dispatch envelope is owned by another executor" in response.json()["detail"].lower()


def test_runtime_profile_read_adapter_refuses_when_capture_load_profile_prerequisites_are_missing(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_profile_read_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-profile-read-missing-batch",
        mock_execution={"outcome": "succeeded"},
    )

    response = _execute_runtime_profile_read_adapter(client, attempt_id, session_identifier)

    assert response.status_code == 409
    assert "capture-load-profile validator" in response.json()["detail"].lower()


def test_repeated_runtime_profile_read_adapter_execution_is_idempotent_with_digest(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    attempt_id, _, _, session_identifier = _prepare_runtime_profile_read_chain(
        client,
        db_session,
        token,
        command_template_code="runtime-profile-read-repeat",
    )

    first = _execute_runtime_profile_read_adapter(client, attempt_id, session_identifier)
    second = _execute_runtime_profile_read_adapter(client, attempt_id, session_identifier)

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["result"]["profile_read_execution_record_id"]
        == second.json()["result"]["profile_read_execution_record_id"]
    )
    assert (
        first.json()["result"]["capture_load_profile_execution_digest"]["summary"]
        == second.json()["result"]["capture_load_profile_execution_digest"]["summary"]
    )
    assert (
        first.json()["result"]["capture_load_profile_terminal_status"]["terminal_status"]
        == second.json()["result"]["capture_load_profile_terminal_status"]["terminal_status"]
    )
    assert second.json()["result"]["already_recorded"] is True


def test_runtime_profile_read_gurux_invocation_mapping_capture_load_profile() -> None:
    request = _build_profile_read_adapter_request_for_tests()

    operation = _map_profile_read_operation_to_gurux_definition(
        RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE
    )
    validated_target = _validate_gurux_capture_load_profile_target(request, operation)
    normalized_request = _normalize_gurux_capture_load_profile_request(
        request,
        validated_target,
    )
    invocation_request = _build_gurux_capture_load_profile_invocation_request(
        normalized_request
    )

    assert operation.interface_class == "profile_generic"
    assert operation.class_id == 7
    assert operation.obis_code == "1.0.99.1.0.255"
    assert validated_target.requested_interval_count == 1
    assert normalized_request.requested_channel_ids == ["00000000-0000-0000-0000-000000000123"]
    assert invocation_request.profile_obis_code == "1.0.99.1.0.255"
    assert invocation_request.selector_name == "capture_period_range"
    assert invocation_request.selector_id == 1
    assert invocation_request.requested_interval_count == 1


def test_runtime_profile_read_gurux_interpreter_maps_rejected_response() -> None:
    interpreted = _interpret_gurux_capture_load_profile_response(
        GuruxProfileReadInvocationResponse(
            acknowledged=False,
            adapter_available=True,
            invocation_status="rejected",
            profile_obis_code="1.0.99.1.0.255",
            payload_snapshot=None,
            response_received_at=datetime.now(UTC).isoformat(),
            error_detail="simulated rejection",
        ),
        requested_outcome=RuntimeCommandOutcome.FAILED,
        error_detail="simulated rejection",
    )

    assert interpreted.adapter_acknowledgment_state.value == "rejected"
    assert interpreted.protocol_stage_outcome.value == "profile_read_failed"
    assert interpreted.execution_outcome == RuntimeCommandOutcome.FAILED
    assert interpreted.error_category.value == "adapter_rejected"


def test_capture_load_profile_execution_digest_projects_valid_execution() -> None:
    request = _build_profile_read_adapter_request_for_tests()
    operation = _map_profile_read_operation_to_gurux_definition(
        RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE
    )
    validated_target = _validate_gurux_capture_load_profile_target(request, operation)
    normalized_request = _normalize_gurux_capture_load_profile_request(request, validated_target)
    invocation_request = _build_gurux_capture_load_profile_invocation_request(normalized_request)
    interpreted = _interpret_gurux_capture_load_profile_response(
        GuruxProfileReadInvocationResponse(
            acknowledged=True,
            adapter_available=True,
            invocation_status="accepted",
            profile_obis_code=invocation_request.profile_obis_code,
            payload_snapshot=request.request_payload["mock_execution"]["reading_batch"],  # type: ignore[index]
            response_received_at=datetime.now(UTC).isoformat(),
        ),
        requested_outcome=RuntimeCommandOutcome.SUCCEEDED,
        error_detail=None,
    )

    result = RuntimeProfileReadExecutionResult(
        status=RuntimeProfileReadExecutionStatus.COMPLETED,
        profile_read_execution_record_id="profile-read-record-1",
        session_identifier="session-profile-1",
        dispatch_envelope_record_id="dispatch-envelope-profile-1",
        delivery_contract_record_id="delivery-contract-1",
        envelope_record_id="envelope-1",
        publication_contract_record_id="publication-contract-1",
        attestation_record_id="attestation-1",
        settlement_record_id="settlement-1",
        reconciliation_record_id="reconciliation-1",
        interpretation_record_id="interpretation-1",
        observation_record_id="observation-1",
        invocation_result_record_id="invocation-1",
        dispatch_request_record_id="dispatch-request-1",
        selection_record_id="selection-1",
        intent_record_id="intent-1",
        closure_record_id="closure-1",
        materialization_record_id="materialization-1",
        post_processing_record_id="post-processing-1",
        disposition_record_id="disposition-1",
        outcome_record_id="outcome-1",
        executor_identifier="worker-runtime-1",
        job_run_id=str(uuid.uuid4()),
        related_command_id=str(uuid.uuid4()),
        command_attempt_id=str(uuid.uuid4()),
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        profile_read_operation=RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE,
        command_category=CommandCategory.PROFILE_CAPTURE,
        adapter_acknowledgment_state=interpreted.adapter_acknowledgment_state,
        protocol_stage_outcome=interpreted.protocol_stage_outcome,
        execution_outcome=interpreted.execution_outcome,
        correlation_id="corr-profile-1",
        request_id="request-profile-1",
        execution_started_at=datetime.now(UTC).isoformat(),
        execution_finished_at=datetime.now(UTC).isoformat(),
        profile_read_batch=interpreted.profile_read_batch,
        adapter_result_summary={
            "gurux_profile_read_operation": operation.model_dump(mode="json"),
            "gurux_profile_read_validated_target": validated_target.model_dump(mode="json"),
            "gurux_profile_read_normalized_request": normalized_request.model_dump(mode="json"),
            "gurux_profile_read_invocation_result": {
                "invocation_status": "accepted"
            },
            "gurux_profile_read_interpreter": interpreted.model_dump(mode="json"),
        },
        adapter_response_snapshot={},
        profile_read_recorded_by_executor_identifier="worker-runtime-1",
        summary="ok",
        lineage=request.lineage,
    )

    digest = _project_capture_load_profile_execution_digest(result)

    assert digest.final_execution_category.value == "completed"
    assert digest.resolved_operation_obis_code == "1.0.99.1.0.255"
    assert digest.load_profile_interval_count == 1
    assert digest.channel_count == 1


def test_capture_load_profile_execution_digest_refuses_incomplete_execution() -> None:
    request = _build_profile_read_adapter_request_for_tests()
    result = RuntimeProfileReadExecutionResult(
        status=RuntimeProfileReadExecutionStatus.COMPLETED,
        profile_read_execution_record_id="profile-read-record-2",
        session_identifier="session-profile-2",
        dispatch_envelope_record_id="dispatch-envelope-profile-2",
        delivery_contract_record_id="delivery-contract-2",
        envelope_record_id="envelope-2",
        publication_contract_record_id="publication-contract-2",
        attestation_record_id="attestation-2",
        settlement_record_id="settlement-2",
        reconciliation_record_id="reconciliation-2",
        interpretation_record_id="interpretation-2",
        observation_record_id="observation-2",
        invocation_result_record_id="invocation-2",
        dispatch_request_record_id="dispatch-request-2",
        selection_record_id="selection-2",
        intent_record_id="intent-2",
        closure_record_id="closure-2",
        materialization_record_id="materialization-2",
        post_processing_record_id="post-processing-2",
        disposition_record_id="disposition-2",
        outcome_record_id="outcome-2",
        executor_identifier="worker-runtime-1",
        job_run_id=str(uuid.uuid4()),
        related_command_id=str(uuid.uuid4()),
        command_attempt_id=str(uuid.uuid4()),
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        profile_read_operation=RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE,
        command_category=CommandCategory.PROFILE_CAPTURE,
        adapter_acknowledgment_state="accepted",
        protocol_stage_outcome="profile_read_completed",
        execution_outcome=RuntimeCommandOutcome.SUCCEEDED,
        correlation_id="corr-profile-2",
        request_id="request-profile-2",
        execution_started_at=datetime.now(UTC).isoformat(),
        execution_finished_at=datetime.now(UTC).isoformat(),
        profile_read_batch=None,
        adapter_result_summary={},
        adapter_response_snapshot={},
        profile_read_recorded_by_executor_identifier="worker-runtime-1",
        summary="ok",
        lineage=request.lineage,
    )

    with pytest.raises(
        ValueError,
        match="Missing staged profile-read adapter artifacts",
    ):
        _project_capture_load_profile_execution_digest(result)


def _build_profile_read_execution_result_for_terminal_status_tests(
    *,
    invocation_status: str = "accepted",
    include_validated_target: bool = True,
    include_normalized_request: bool = True,
    include_invocation_result: bool = True,
    include_interpreter: bool = True,
    include_profile_batch: bool = True,
    acknowledged: bool = True,
    execution_outcome: RuntimeCommandOutcome = RuntimeCommandOutcome.SUCCEEDED,
) -> tuple[RuntimeProfileReadExecutionResult, object]:
    request = _build_profile_read_adapter_request_for_tests()
    operation = _map_profile_read_operation_to_gurux_definition(
        RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE
    )
    validated_target = _validate_gurux_capture_load_profile_target(request, operation)
    normalized_request = _normalize_gurux_capture_load_profile_request(request, validated_target)
    invocation_request = _build_gurux_capture_load_profile_invocation_request(normalized_request)
    base_interpreted = _interpret_gurux_capture_load_profile_response(
        GuruxProfileReadInvocationResponse(
            acknowledged=True,
            adapter_available=True,
            invocation_status="accepted",
            profile_obis_code=invocation_request.profile_obis_code,
            payload_snapshot=request.request_payload["mock_execution"]["reading_batch"],  # type: ignore[index]
            response_received_at=datetime.now(UTC).isoformat(),
            error_detail="simulated-terminal-status",
        ),
        requested_outcome=RuntimeCommandOutcome.SUCCEEDED,
        error_detail="simulated-terminal-status",
    )
    base_result = RuntimeProfileReadExecutionResult(
        status=RuntimeProfileReadExecutionStatus.COMPLETED,
        profile_read_execution_record_id="profile-read-terminal-record",
        session_identifier="session-profile-terminal",
        dispatch_envelope_record_id="dispatch-envelope-terminal",
        delivery_contract_record_id="delivery-contract-terminal",
        envelope_record_id="envelope-terminal",
        publication_contract_record_id="publication-contract-terminal",
        attestation_record_id="attestation-terminal",
        settlement_record_id="settlement-terminal",
        reconciliation_record_id="reconciliation-terminal",
        interpretation_record_id="interpretation-terminal",
        observation_record_id="observation-terminal",
        invocation_result_record_id="invocation-terminal",
        dispatch_request_record_id="dispatch-request-terminal",
        selection_record_id="selection-terminal",
        intent_record_id="intent-terminal",
        closure_record_id="closure-terminal",
        materialization_record_id="materialization-terminal",
        post_processing_record_id="post-processing-terminal",
        disposition_record_id="disposition-terminal",
        outcome_record_id="outcome-terminal",
        executor_identifier="worker-runtime-1",
        job_run_id=str(uuid.uuid4()),
        related_command_id=str(uuid.uuid4()),
        command_attempt_id=str(uuid.uuid4()),
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        profile_read_operation=RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE,
        command_category=CommandCategory.PROFILE_CAPTURE,
        adapter_acknowledgment_state=base_interpreted.adapter_acknowledgment_state,
        protocol_stage_outcome=base_interpreted.protocol_stage_outcome,
        execution_outcome=base_interpreted.execution_outcome,
        correlation_id="corr-profile-terminal",
        request_id="request-profile-terminal",
        execution_started_at=datetime.now(UTC).isoformat(),
        execution_finished_at=datetime.now(UTC).isoformat(),
        profile_read_batch=base_interpreted.profile_read_batch,
        adapter_result_summary={
            "gurux_profile_read_operation": operation.model_dump(mode="json"),
            "gurux_profile_read_validated_target": validated_target.model_dump(mode="json"),
            "gurux_profile_read_normalized_request": normalized_request.model_dump(mode="json"),
            "gurux_profile_read_invocation_result": {"invocation_status": "accepted"},
            "gurux_profile_read_interpreter": base_interpreted.model_dump(mode="json"),
        },
        adapter_response_snapshot={},
        error_category=base_interpreted.error_category,
        error_detail=base_interpreted.error_detail,
        profile_read_recorded_by_executor_identifier="worker-runtime-1",
        summary="terminal-status-test",
        lineage=request.lineage,
    )
    digest = _project_capture_load_profile_execution_digest(base_result)

    payload_snapshot = (
        request.request_payload["mock_execution"]["reading_batch"]  # type: ignore[index]
        if include_profile_batch
        else None
    )
    interpreted = (
        _interpret_gurux_capture_load_profile_response(
            GuruxProfileReadInvocationResponse(
                acknowledged=acknowledged,
                adapter_available=invocation_status != "unavailable",
                invocation_status=invocation_status,
                profile_obis_code=invocation_request.profile_obis_code,
                payload_snapshot=payload_snapshot if acknowledged else None,
                response_received_at=datetime.now(UTC).isoformat(),
                error_detail="simulated-terminal-status",
            ),
            requested_outcome=execution_outcome,
            error_detail="simulated-terminal-status",
        )
        if include_interpreter
        else None
    )
    result = base_result.model_copy(update={
        "adapter_acknowledgment_state": (
            interpreted.adapter_acknowledgment_state if interpreted is not None else base_result.adapter_acknowledgment_state
        ),
        "protocol_stage_outcome": (
            interpreted.protocol_stage_outcome if interpreted is not None else base_result.protocol_stage_outcome
        ),
        "execution_outcome": execution_outcome,
        "profile_read_batch": (interpreted.profile_read_batch if interpreted is not None else None),
        "error_category": (interpreted.error_category if interpreted is not None else None),
        "error_detail": (interpreted.error_detail if interpreted is not None else None),
        "capture_load_profile_execution_digest": digest,
        "adapter_result_summary": {
            "gurux_profile_read_operation": operation.model_dump(mode="json"),
            **(
                {"gurux_profile_read_validated_target": validated_target.model_dump(mode="json")}
                if include_validated_target
                else {}
            ),
            **(
                {"gurux_profile_read_normalized_request": normalized_request.model_dump(mode="json")}
                if include_normalized_request
                else {}
            ),
            **(
                {"gurux_profile_read_invocation_result": {"invocation_status": invocation_status}}
                if include_invocation_result
                else {}
            ),
            **(
                {"gurux_profile_read_interpreter": interpreted.model_dump(mode="json")}
                if include_interpreter and interpreted is not None
                else {}
            ),
        },
    })
    return result, digest


def test_capture_load_profile_terminal_status_projects_acknowledged() -> None:
    result, digest = _build_profile_read_execution_result_for_terminal_status_tests()
    terminal_status = _project_capture_load_profile_terminal_status(result, digest)
    assert terminal_status.terminal_status.value == "acknowledged"


def test_capture_load_profile_terminal_status_projects_rejected() -> None:
    result, digest = _build_profile_read_execution_result_for_terminal_status_tests(
        invocation_status="rejected",
        acknowledged=False,
        execution_outcome=RuntimeCommandOutcome.FAILED,
    )
    terminal_status = _project_capture_load_profile_terminal_status(result, digest)
    assert terminal_status.terminal_status.value == "rejected"


def test_capture_load_profile_terminal_status_projects_unavailable() -> None:
    result, digest = _build_profile_read_execution_result_for_terminal_status_tests(
        invocation_status="unavailable",
        acknowledged=False,
        execution_outcome=RuntimeCommandOutcome.FAILED,
    )
    terminal_status = _project_capture_load_profile_terminal_status(result, digest)
    assert terminal_status.terminal_status.value == "unavailable"


def test_capture_load_profile_terminal_status_projects_blocked_pre_invocation() -> None:
    result, digest = _build_profile_read_execution_result_for_terminal_status_tests(
        include_validated_target=False,
        include_normalized_request=False,
        include_invocation_result=False,
        include_interpreter=False,
        include_profile_batch=False,
    )
    terminal_status = _project_capture_load_profile_terminal_status(result, digest)
    assert terminal_status.terminal_status.value == "blocked_pre_invocation"


def test_capture_load_profile_terminal_status_projects_blocked_mid_pipeline() -> None:
    result, digest = _build_profile_read_execution_result_for_terminal_status_tests(
        include_invocation_result=False,
        include_interpreter=False,
        include_profile_batch=False,
    )
    terminal_status = _project_capture_load_profile_terminal_status(result, digest)
    assert terminal_status.terminal_status.value == "blocked_mid_pipeline"


def test_capture_load_profile_terminal_status_projects_unusable_response() -> None:
    result, digest = _build_profile_read_execution_result_for_terminal_status_tests(
        include_interpreter=False,
        include_profile_batch=False,
    )
    terminal_status = _project_capture_load_profile_terminal_status(result, digest)
    assert terminal_status.terminal_status.value == "unusable_response"
