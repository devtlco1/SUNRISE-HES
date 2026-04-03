from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from app.core.config import settings
from app.modules.connectivity.enums import (
    ConnectivitySessionStatus,
    ConnectivityTransportType,
    ProtocolFamily,
)
from app.modules.events.enums import EventSeverity, EventState
from app.modules.readings.enums import ReadingBatchStatus, ReadingSourceType, ReadingType, SnapshotType
from app.runtime.adapters.base import BaseRuntimeAdapter
from app.runtime.adapters.gurux_tcp_ingress import (
    LiveTcpDlmsSessionConfig,
    LiveTcpOnDemandReadExecution,
    LiveTcpProfileReadExecution,
    LiveTcpRelayControlExecution,
    execute_billing_snapshot_over_tcp_ingress,
    execute_capture_load_profile_over_tcp_ingress,
    execute_relay_control_over_tcp_ingress,
)
from app.runtime.contracts import (
    ProtocolExecutionPlan,
    RuntimeOnDemandReadAdapterAcknowledgmentState,
    RuntimeOnDemandReadAdapterRequest,
    RuntimeOnDemandReadErrorCategory,
    RuntimeOnDemandReadExecutionResult,
    RuntimeOnDemandReadExecutionStatus,
    RuntimeOnDemandReadOperation,
    RuntimeOnDemandReadProtocolStageOutcome,
    RuntimeRelayControlAdapterAcknowledgmentState,
    RuntimeRelayControlAdapterRequest,
    RuntimeRelayControlErrorCategory,
    RuntimeRelayControlExecutionResult,
    RuntimeRelayControlExecutionStatus,
    RuntimeRelayControlOperation,
    RuntimeRelayControlProtocolStageOutcome,
    RuntimeProfileReadAdapterAcknowledgmentState,
    RuntimeProfileReadAdapterRequest,
    RuntimeProfileReadErrorCategory,
    RuntimeProfileReadExecutionResult,
    RuntimeProfileReadExecutionStatus,
    RuntimeProfileReadOperation,
    RuntimeProfileReadProtocolStageOutcome,
    RuntimeCommandOutcome,
    RuntimeCommandResult,
    RuntimeEventPayload,
    RuntimeLoadProfileIntervalPayload,
    RuntimeReadingBatchPayload,
    RuntimeReadingPayload,
    RuntimeRegisterSnapshotPayload,
    RuntimeSessionResult,
)
from app.runtime.services.runtime_secret_refs import resolve_runtime_secret_ref
from app.runtime.services.tcp_meter_ingress import (
    borrow_runtime_tcp_meter_ingress_connection,
    get_runtime_tcp_meter_ingress_status,
    mark_runtime_tcp_meter_ingress_connection_dead,
)


class DlmsCosemRuntimeAdapter(BaseRuntimeAdapter):
    adapter_key = "dlms-cosem-runtime"
    supported_protocol_families = (ProtocolFamily.DLMS_COSEM,)

    def execute(self, plan: ProtocolExecutionPlan) -> RuntimeCommandResult:
        raise NotImplementedError(
            "DLMS/COSEM runtime execution is intentionally not implemented yet. "
            "This adapter only defines the worker-facing contract boundary."
        )

    def supports_relay_control(self, request: RuntimeRelayControlAdapterRequest) -> bool:
        return request.operation in {
            RuntimeRelayControlOperation.DISCONNECT,
            RuntimeRelayControlOperation.RECONNECT,
        }

    def supports_profile_read(self, request: RuntimeProfileReadAdapterRequest) -> bool:
        return request.operation == RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE

    def supports_on_demand_read(self, request: RuntimeOnDemandReadAdapterRequest) -> bool:
        return request.operation == RuntimeOnDemandReadOperation.READ_BILLING_SNAPSHOT


class GuruxDlmsAdapterBridge(DlmsCosemRuntimeAdapter):
    adapter_key = "gurux-dlms-bridge"

    def execute(self, plan: ProtocolExecutionPlan) -> RuntimeCommandResult:
        now = datetime.now(UTC)
        payload = plan.command.normalized_payload or {}
        mock_execution = payload.get("mock_execution", {}) if isinstance(payload, dict) else {}
        outcome = RuntimeCommandOutcome(mock_execution.get("outcome", RuntimeCommandOutcome.SUCCEEDED.value))

        session_result = RuntimeSessionResult(
            status=_map_outcome_to_session_status(outcome),
            session_purpose=plan.session_purpose,
            started_at=now,
            ended_at=now,
            request_id=plan.execution_context.request_id,
            correlation_id=plan.execution_context.correlation_id,
            handshake_stage=plan.stages[-1].value if plan.stages else None,
            bytes_sent=int(mock_execution.get("bytes_sent", 96)),
            bytes_received=int(mock_execution.get("bytes_received", 192)),
            transport_latency_ms=int(mock_execution.get("latency_ms", 25)),
            error_code=mock_execution.get("error_code"),
            error_message=mock_execution.get("error_message"),
            metadata={
                "placeholder": True,
                "adapter_key": self.adapter_key,
                "intent": plan.intent.value,
                "stages": [stage.value for stage in plan.stages],
            },
        )

        reading_batch = None
        explicit_reading_batch = mock_execution.get("reading_batch")
        if isinstance(explicit_reading_batch, dict):
            reading_batch = RuntimeReadingBatchPayload.model_validate(explicit_reading_batch)
        elif mock_execution.get("include_placeholder_readings"):
            reading_batch = RuntimeReadingBatchPayload(
                source_type=ReadingSourceType.COMMAND_RESULT,
                captured_at=now,
                received_at=now,
                status=ReadingBatchStatus.RECEIVED,
                correlation_id=plan.execution_context.correlation_id,
                reading_context={"placeholder": True, "intent": plan.intent.value},
                readings=[
                    RuntimeReadingPayload(
                        obis_code="1.0.1.8.0.255",
                        reading_type=ReadingType.REGISTER,
                        value_numeric="123.456",
                        unit="kWh",
                        captured_at=now,
                        metadata={"placeholder": True},
                    )
                ],
                register_snapshots=[
                    RuntimeRegisterSnapshotPayload(
                        snapshot_type="billing",
                        captured_at=now,
                        payload={"1.0.1.8.0.255": "123.456"},
                    )
                ]
                if mock_execution.get("include_placeholder_snapshots")
                else [],
                load_profile_intervals=[
                    RuntimeLoadProfileIntervalPayload.model_validate(item)
                    for item in mock_execution.get("placeholder_intervals", [])
                ],
            )

        explicit_events = mock_execution.get("events")
        if isinstance(explicit_events, list):
            events = [RuntimeEventPayload.model_validate(event) for event in explicit_events]
        else:
            events = []
        if not events and mock_execution.get("include_placeholder_events"):
            events.append(
                RuntimeEventPayload(
                    event_code="RUNTIME_PLACEHOLDER_EVENT",
                    event_name="Runtime Placeholder Event",
                    severity=EventSeverity.INFO,
                    event_state=EventState.OPEN,
                    occurred_at=now,
                    normalized_payload={"placeholder": True, "intent": plan.intent.value},
                )
            )

        return RuntimeCommandResult(
            outcome=outcome,
            result_summary={
                "adapter_key": self.adapter_key,
                "placeholder": True,
                "intent": plan.intent.value,
            },
            response_snapshot={
                "adapter": self.adapter_key,
                "placeholder": True,
                "stages": [stage.value for stage in plan.stages],
            },
            latest_error_code=session_result.error_code,
            latest_error_message=session_result.error_message,
            session_result=session_result,
            reading_batch=reading_batch,
            events=events,
        )

    def execute_relay_control(
        self,
        request: RuntimeRelayControlAdapterRequest,
    ) -> RuntimeRelayControlExecutionResult:
        now = datetime.now(UTC)
        gurux_operation = _map_relay_control_operation_to_gurux_definition(
            request.operation
        )
        live_execution = _execute_live_tcp_relay_control_if_available(
            request,
            gurux_operation=gurux_operation,
        )
        if live_execution is not None:
            trace_references = request.trace_references
            live_execution_succeeded = live_execution.invocation_status == "acknowledged"
            adapter_acknowledgment_state = (
                RuntimeRelayControlAdapterAcknowledgmentState.ACCEPTED
                if live_execution_succeeded
                else RuntimeRelayControlAdapterAcknowledgmentState.REJECTED
            )
            protocol_stage_outcome = (
                RuntimeRelayControlProtocolStageOutcome.RELAY_OPERATION_COMPLETED
                if live_execution_succeeded
                else RuntimeRelayControlProtocolStageOutcome.RELAY_OPERATION_FAILED
            )
            execution_outcome = (
                RuntimeCommandOutcome.SUCCEEDED
                if live_execution_succeeded
                else RuntimeCommandOutcome.FAILED
            )
            error_category = None
            if not live_execution_succeeded:
                error_category = (
                    RuntimeRelayControlErrorCategory.ADAPTER_REJECTED
                    if live_execution.invocation_status == "rejected"
                    else RuntimeRelayControlErrorCategory.EXECUTION_FAILED
                )
            summary = (
                "Relay-control completed over the bound live TCP ingress session."
                if live_execution_succeeded
                else "Relay-control failed over the bound live TCP ingress session."
            )
            return RuntimeRelayControlExecutionResult(
                status=RuntimeRelayControlExecutionStatus.COMPLETED,
                relay_control_execution_record_id=(
                    "runtime-relay-control:"
                    f"{request.execution_context.command_attempt_id}:{request.execution_context.request_id or request.execution_context.command_id}"
                ),
                session_identifier=str(trace_references["session_identifier"]),
                dispatch_envelope_record_id=request.dispatch_envelope_record_id,
                delivery_contract_record_id=str(trace_references["delivery_contract_record_id"]),
                envelope_record_id=str(trace_references["envelope_record_id"]),
                publication_contract_record_id=str(
                    trace_references["publication_contract_record_id"]
                ),
                attestation_record_id=str(trace_references["attestation_record_id"]),
                settlement_record_id=str(trace_references["settlement_record_id"]),
                reconciliation_record_id=str(trace_references["reconciliation_record_id"]),
                interpretation_record_id=str(trace_references["interpretation_record_id"]),
                observation_record_id=str(trace_references["observation_record_id"]),
                invocation_result_record_id=str(
                    trace_references["invocation_result_record_id"]
                ),
                dispatch_request_record_id=str(trace_references["dispatch_request_record_id"]),
                selection_record_id=str(trace_references["selection_record_id"]),
                intent_record_id=str(trace_references["intent_record_id"]),
                closure_record_id=str(trace_references["closure_record_id"]),
                materialization_record_id=str(trace_references["materialization_record_id"]),
                post_processing_record_id=str(trace_references["post_processing_record_id"]),
                disposition_record_id=str(trace_references["disposition_record_id"]),
                outcome_record_id=str(trace_references["outcome_record_id"]),
                executor_identifier=str(request.execution_context.worker_identifier),
                job_run_id=str(request.execution_context.job_run_id),
                related_command_id=str(request.execution_context.command_id),
                command_attempt_id=str(request.execution_context.command_attempt_id),
                adapter_key=self.adapter_key,
                protocol_family=request.protocol_family,
                relay_operation=request.operation,
                command_category=request.command_category,
                adapter_acknowledgment_state=adapter_acknowledgment_state,
                protocol_stage_outcome=protocol_stage_outcome,
                execution_outcome=execution_outcome,
                correlation_id=request.execution_context.correlation_id,
                request_id=request.execution_context.request_id,
                execution_started_at=now.isoformat(),
                execution_finished_at=now.isoformat(),
                adapter_result_summary={
                    "adapter_key": self.adapter_key,
                    "operation": request.operation.value,
                    "protocol_family": request.protocol_family.value,
                    "vertical_slice": "relay_control",
                    "live_tcp_ingress": {
                        "used_bound_connection": bool(
                            live_execution.protocol_trace.get("used_bound_connection", True)
                        ),
                        "invocation_status": live_execution.invocation_status,
                        "before_state": (
                            live_execution.before_state.__dict__
                            if live_execution.before_state is not None
                            else None
                        ),
                        "after_state": (
                            live_execution.after_state.__dict__
                            if live_execution.after_state is not None
                            else None
                        ),
                        "error_detail": live_execution.error_detail,
                        "protocol_trace": live_execution.protocol_trace,
                        "raw_frames": live_execution.raw_frames,
                        "bytes_sent": live_execution.bytes_sent,
                        "bytes_received": live_execution.bytes_received,
                    },
                },
                adapter_response_snapshot={
                    "adapter": self.adapter_key,
                    "operation": request.operation.value,
                    "target_meter_id": str(request.target.meter_id),
                    "endpoint_id": str(request.target.endpoint_id),
                    "protocol_profile_id": str(request.target.protocol_association_profile_id),
                    "live_tcp_ingress": {
                        "invocation_status": live_execution.invocation_status,
                        "before_state": (
                            live_execution.before_state.__dict__
                            if live_execution.before_state is not None
                            else None
                        ),
                        "after_state": (
                            live_execution.after_state.__dict__
                            if live_execution.after_state is not None
                            else None
                        ),
                        "error_detail": live_execution.error_detail,
                        "protocol_trace": live_execution.protocol_trace,
                    },
                },
                error_category=error_category,
                error_detail=live_execution.error_detail,
                relay_control_recorded_by_executor_identifier=str(
                    request.execution_context.worker_identifier
                ),
                already_recorded=False,
                summary=summary,
                lineage=request.lineage,
            )
        payload = request.normalized_payload or request.request_payload or {}
        mock_execution = payload.get("mock_execution", {}) if isinstance(payload, dict) else {}
        resolved_transport_profile = _resolve_gurux_relay_control_transport_profile(
            request,
            gurux_operation,
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
        invocation_request = _build_gurux_relay_control_invocation_stub_request(
            normalized_request,
        )
        invocation_response = _invoke_gurux_relay_control_stub(
            invocation_request,
            mock_execution=mock_execution,
        )
        requested_outcome = RuntimeCommandOutcome(
            mock_execution.get("outcome", RuntimeCommandOutcome.SUCCEEDED.value)
        )
        error_detail = mock_execution.get("error_detail") or mock_execution.get("error_message")
        interpreted_result = _interpret_gurux_relay_control_stub_response(
            invocation_response,
            requested_outcome=requested_outcome,
            error_detail=error_detail,
        )
        execution_audit_summary = _build_gurux_relay_control_execution_audit_summary(
            request=request,
            gurux_operation=gurux_operation,
            resolved_transport_profile=resolved_transport_profile,
            validated_target=validated_target,
            normalized_request=normalized_request,
            invocation_response=invocation_response,
            interpreted_result=interpreted_result,
        )
        execution_phase_progression = _project_gurux_relay_control_execution_phase_state(
            request=request,
            gurux_operation=gurux_operation,
            resolved_transport_profile=resolved_transport_profile,
            validated_target=validated_target,
            normalized_request=normalized_request,
            invocation_response=invocation_response,
            interpreted_result=interpreted_result,
            execution_audit_summary=execution_audit_summary,
        )
        terminal_adapter_status = _project_gurux_relay_control_terminal_adapter_status(
            request=request,
            execution_phase_progression=execution_phase_progression,
            execution_audit_summary=execution_audit_summary,
            interpreted_result=interpreted_result,
        )

        trace_references = request.trace_references
        return RuntimeRelayControlExecutionResult(
            status=RuntimeRelayControlExecutionStatus.COMPLETED,
            relay_control_execution_record_id=(
                "runtime-relay-control:"
                f"{request.execution_context.command_attempt_id}:{request.execution_context.request_id or request.execution_context.command_id}"
            ),
            session_identifier=str(trace_references["session_identifier"]),
            dispatch_envelope_record_id=request.dispatch_envelope_record_id,
            delivery_contract_record_id=str(trace_references["delivery_contract_record_id"]),
            envelope_record_id=str(trace_references["envelope_record_id"]),
            publication_contract_record_id=str(
                trace_references["publication_contract_record_id"]
            ),
            attestation_record_id=str(trace_references["attestation_record_id"]),
            settlement_record_id=str(trace_references["settlement_record_id"]),
            reconciliation_record_id=str(trace_references["reconciliation_record_id"]),
            interpretation_record_id=str(trace_references["interpretation_record_id"]),
            observation_record_id=str(trace_references["observation_record_id"]),
            invocation_result_record_id=str(
                trace_references["invocation_result_record_id"]
            ),
            dispatch_request_record_id=str(trace_references["dispatch_request_record_id"]),
            selection_record_id=str(trace_references["selection_record_id"]),
            intent_record_id=str(trace_references["intent_record_id"]),
            closure_record_id=str(trace_references["closure_record_id"]),
            materialization_record_id=str(trace_references["materialization_record_id"]),
            post_processing_record_id=str(trace_references["post_processing_record_id"]),
            disposition_record_id=str(trace_references["disposition_record_id"]),
            outcome_record_id=str(trace_references["outcome_record_id"]),
            executor_identifier=str(request.execution_context.worker_identifier),
            job_run_id=str(request.execution_context.job_run_id),
            related_command_id=str(request.execution_context.command_id),
            command_attempt_id=str(request.execution_context.command_attempt_id),
            adapter_key=self.adapter_key,
            protocol_family=request.protocol_family,
            relay_operation=request.operation,
            command_category=request.command_category,
            adapter_acknowledgment_state=interpreted_result.adapter_acknowledgment_state,
            protocol_stage_outcome=interpreted_result.protocol_stage_outcome,
            execution_outcome=interpreted_result.execution_outcome,
            correlation_id=request.execution_context.correlation_id,
            request_id=request.execution_context.request_id,
            execution_started_at=now.isoformat(),
            execution_finished_at=now.isoformat(),
            adapter_result_summary={
                "adapter_key": self.adapter_key,
                "operation": request.operation.value,
                "protocol_family": request.protocol_family.value,
                "adapter_acknowledged": invocation_response.acknowledged,
                "vertical_slice": "relay_control",
                "gurux_operation": gurux_operation.model_dump(mode="json"),
                "gurux_resolved_transport_profile": resolved_transport_profile.model_dump(
                    mode="json"
                ),
                "gurux_validated_target": validated_target.model_dump(mode="json"),
                "gurux_normalized_request": normalized_request.model_dump(mode="json"),
                "gurux_invocation_stub": invocation_response.model_dump(mode="json"),
                "gurux_interpreter": interpreted_result.model_dump(mode="json"),
                "gurux_execution_audit_summary": execution_audit_summary.model_dump(
                    mode="json"
                ),
                "gurux_execution_phase_progression": execution_phase_progression.model_dump(
                    mode="json"
                ),
                "gurux_terminal_adapter_status": terminal_adapter_status.model_dump(
                    mode="json"
                ),
            },
            adapter_response_snapshot={
                "adapter": self.adapter_key,
                "operation": request.operation.value,
                "target_meter_id": str(request.target.meter_id),
                "endpoint_id": str(request.target.endpoint_id),
                "protocol_profile_id": str(request.target.protocol_association_profile_id),
                "gurux_operation": gurux_operation.model_dump(mode="json"),
                "gurux_resolved_transport_profile": resolved_transport_profile.model_dump(
                    mode="json"
                ),
                "gurux_validated_target": validated_target.model_dump(mode="json"),
                "gurux_normalized_request": normalized_request.model_dump(mode="json"),
                "gurux_invocation_request": invocation_request.model_dump(mode="json"),
                "gurux_invocation_stub": invocation_response.model_dump(mode="json"),
                "gurux_interpreter": interpreted_result.model_dump(mode="json"),
                "gurux_execution_audit_summary": execution_audit_summary.model_dump(
                    mode="json"
                ),
                "gurux_execution_phase_progression": execution_phase_progression.model_dump(
                    mode="json"
                ),
                "gurux_terminal_adapter_status": terminal_adapter_status.model_dump(
                    mode="json"
                ),
            },
            error_category=interpreted_result.error_category,
            error_detail=interpreted_result.error_detail,
            relay_control_recorded_by_executor_identifier=str(
                request.execution_context.worker_identifier
            ),
            already_recorded=False,
            summary=interpreted_result.interpreter_summary,
            lineage=request.lineage,
        )

    def execute_on_demand_read(
        self,
        request: RuntimeOnDemandReadAdapterRequest,
    ) -> RuntimeOnDemandReadExecutionResult:
        now = datetime.now(UTC)
        payload = request.normalized_payload or request.request_payload or {}
        live_execution = _execute_live_tcp_on_demand_read_if_available(request)
        if live_execution is not None:
            register_snapshot = RuntimeRegisterSnapshotPayload(
                snapshot_type=SnapshotType.BILLING,
                captured_at=now,
                payload=live_execution.register_snapshot_payload,
            )
            trace_references = request.trace_references
            return RuntimeOnDemandReadExecutionResult(
                status=RuntimeOnDemandReadExecutionStatus.COMPLETED,
                on_demand_read_execution_record_id=(
                    "runtime-on-demand-read:"
                    f"{request.execution_context.command_attempt_id}:{request.execution_context.request_id or request.execution_context.command_id}"
                ),
                session_identifier=str(trace_references["session_identifier"]),
                dispatch_envelope_record_id=request.dispatch_envelope_record_id,
                delivery_contract_record_id=str(trace_references["delivery_contract_record_id"]),
                envelope_record_id=str(trace_references["envelope_record_id"]),
                publication_contract_record_id=str(
                    trace_references["publication_contract_record_id"]
                ),
                attestation_record_id=str(trace_references["attestation_record_id"]),
                settlement_record_id=str(trace_references["settlement_record_id"]),
                reconciliation_record_id=str(trace_references["reconciliation_record_id"]),
                interpretation_record_id=str(trace_references["interpretation_record_id"]),
                observation_record_id=str(trace_references["observation_record_id"]),
                invocation_result_record_id=str(trace_references["invocation_result_record_id"]),
                dispatch_request_record_id=str(trace_references["dispatch_request_record_id"]),
                selection_record_id=str(trace_references["selection_record_id"]),
                intent_record_id=str(trace_references["intent_record_id"]),
                closure_record_id=str(trace_references["closure_record_id"]),
                materialization_record_id=str(trace_references["materialization_record_id"]),
                post_processing_record_id=str(trace_references["post_processing_record_id"]),
                disposition_record_id=str(trace_references["disposition_record_id"]),
                outcome_record_id=str(trace_references["outcome_record_id"]),
                executor_identifier=str(request.execution_context.worker_identifier),
                job_run_id=str(request.execution_context.job_run_id),
                related_command_id=str(request.execution_context.command_id),
                command_attempt_id=str(request.execution_context.command_attempt_id),
                adapter_key=self.adapter_key,
                protocol_family=request.protocol_family,
                on_demand_read_operation=request.operation,
                snapshot_type=SnapshotType.BILLING,
                command_category=request.command_category,
                adapter_acknowledgment_state=(
                    RuntimeOnDemandReadAdapterAcknowledgmentState.ACCEPTED
                ),
                protocol_stage_outcome=(
                    RuntimeOnDemandReadProtocolStageOutcome.BILLING_SNAPSHOT_COMPLETED
                ),
                execution_outcome=RuntimeCommandOutcome.SUCCEEDED,
                correlation_id=request.execution_context.correlation_id,
                request_id=request.execution_context.request_id,
                execution_started_at=now.isoformat(),
                execution_finished_at=now.isoformat(),
                register_snapshot=register_snapshot,
                adapter_result_summary={
                    "adapter_key": self.adapter_key,
                    "operation": request.operation.value,
                    "protocol_family": request.protocol_family.value,
                    "vertical_slice": "on_demand_read",
                    "snapshot_type": SnapshotType.BILLING.value,
                    "register_snapshot_present": True,
                    "live_tcp_ingress": True,
                    "bytes_sent": live_execution.bytes_sent,
                    "bytes_received": live_execution.bytes_received,
                    "protocol_trace": live_execution.protocol_trace,
                },
                adapter_response_snapshot={
                    "adapter": self.adapter_key,
                    "operation": request.operation.value,
                    "target_meter_id": str(request.target.meter_id),
                    "endpoint_id": str(request.target.endpoint_id),
                    "protocol_profile_id": str(request.target.protocol_association_profile_id),
                    "snapshot_type": SnapshotType.BILLING.value,
                    "register_snapshot": register_snapshot.model_dump(mode="json"),
                    "raw_frames": live_execution.raw_frames,
                },
                error_category=None,
                error_detail=None,
                on_demand_read_recorded_by_executor_identifier=str(
                    request.execution_context.worker_identifier
                ),
                already_recorded=False,
                summary=(
                    "ON_DEMAND_READ billing snapshot completed through the live TCP ingress "
                    "adapter path."
                ),
                lineage=request.lineage,
            )

        mock_execution = payload.get("mock_execution", {}) if isinstance(payload, dict) else {}
        requested_outcome = RuntimeCommandOutcome(
            mock_execution.get("outcome", RuntimeCommandOutcome.SUCCEEDED.value)
        )
        explicit_snapshot = mock_execution.get("register_snapshot")
        if isinstance(explicit_snapshot, dict):
            register_snapshot = RuntimeRegisterSnapshotPayload.model_validate(explicit_snapshot)
        else:
            register_snapshot = RuntimeRegisterSnapshotPayload(
                snapshot_type=SnapshotType.BILLING,
                captured_at=now,
                payload={
                    "1.0.1.8.0.255": mock_execution.get("billing_import_wh", "123.456"),
                    "1.0.2.8.0.255": mock_execution.get("billing_export_wh", "0.000"),
                },
            )
        if requested_outcome == RuntimeCommandOutcome.SUCCEEDED:
            adapter_acknowledgment_state = (
                RuntimeOnDemandReadAdapterAcknowledgmentState.ACCEPTED
            )
            protocol_stage_outcome = (
                RuntimeOnDemandReadProtocolStageOutcome.BILLING_SNAPSHOT_COMPLETED
            )
            error_category = None
            error_detail = None
            summary = "ON_DEMAND_READ billing snapshot completed through the real adapter contract seam."
        else:
            adapter_acknowledgment_state = (
                RuntimeOnDemandReadAdapterAcknowledgmentState.REJECTED
            )
            protocol_stage_outcome = (
                RuntimeOnDemandReadProtocolStageOutcome.BILLING_SNAPSHOT_FAILED
            )
            error_category = RuntimeOnDemandReadErrorCategory.EXECUTION_FAILED
            error_detail = mock_execution.get("error_detail") or mock_execution.get("error_message")
            summary = "ON_DEMAND_READ billing snapshot failed through the real adapter contract seam."

        trace_references = request.trace_references
        return RuntimeOnDemandReadExecutionResult(
            status=RuntimeOnDemandReadExecutionStatus.COMPLETED,
            on_demand_read_execution_record_id=(
                "runtime-on-demand-read:"
                f"{request.execution_context.command_attempt_id}:{request.execution_context.request_id or request.execution_context.command_id}"
            ),
            session_identifier=str(trace_references["session_identifier"]),
            dispatch_envelope_record_id=request.dispatch_envelope_record_id,
            delivery_contract_record_id=str(trace_references["delivery_contract_record_id"]),
            envelope_record_id=str(trace_references["envelope_record_id"]),
            publication_contract_record_id=str(
                trace_references["publication_contract_record_id"]
            ),
            attestation_record_id=str(trace_references["attestation_record_id"]),
            settlement_record_id=str(trace_references["settlement_record_id"]),
            reconciliation_record_id=str(trace_references["reconciliation_record_id"]),
            interpretation_record_id=str(trace_references["interpretation_record_id"]),
            observation_record_id=str(trace_references["observation_record_id"]),
            invocation_result_record_id=str(trace_references["invocation_result_record_id"]),
            dispatch_request_record_id=str(trace_references["dispatch_request_record_id"]),
            selection_record_id=str(trace_references["selection_record_id"]),
            intent_record_id=str(trace_references["intent_record_id"]),
            closure_record_id=str(trace_references["closure_record_id"]),
            materialization_record_id=str(trace_references["materialization_record_id"]),
            post_processing_record_id=str(trace_references["post_processing_record_id"]),
            disposition_record_id=str(trace_references["disposition_record_id"]),
            outcome_record_id=str(trace_references["outcome_record_id"]),
            executor_identifier=str(request.execution_context.worker_identifier),
            job_run_id=str(request.execution_context.job_run_id),
            related_command_id=str(request.execution_context.command_id),
            command_attempt_id=str(request.execution_context.command_attempt_id),
            adapter_key=self.adapter_key,
            protocol_family=request.protocol_family,
            on_demand_read_operation=request.operation,
            snapshot_type=SnapshotType.BILLING,
            command_category=request.command_category,
            adapter_acknowledgment_state=adapter_acknowledgment_state,
            protocol_stage_outcome=protocol_stage_outcome,
            execution_outcome=requested_outcome,
            correlation_id=request.execution_context.correlation_id,
            request_id=request.execution_context.request_id,
            execution_started_at=now.isoformat(),
            execution_finished_at=now.isoformat(),
            register_snapshot=register_snapshot,
            adapter_result_summary={
                "adapter_key": self.adapter_key,
                "operation": request.operation.value,
                "protocol_family": request.protocol_family.value,
                "vertical_slice": "on_demand_read",
                "snapshot_type": SnapshotType.BILLING.value,
                "register_snapshot_present": register_snapshot is not None,
            },
            adapter_response_snapshot={
                "adapter": self.adapter_key,
                "operation": request.operation.value,
                "target_meter_id": str(request.target.meter_id),
                "endpoint_id": str(request.target.endpoint_id),
                "protocol_profile_id": str(request.target.protocol_association_profile_id),
                "snapshot_type": SnapshotType.BILLING.value,
                "register_snapshot": register_snapshot.model_dump(mode="json"),
            },
            error_category=error_category,
            error_detail=error_detail,
            on_demand_read_recorded_by_executor_identifier=str(
                request.execution_context.worker_identifier
            ),
            already_recorded=False,
            summary=summary,
            lineage=request.lineage,
        )

    def execute_profile_read(
        self,
        request: RuntimeProfileReadAdapterRequest,
    ) -> RuntimeProfileReadExecutionResult:
        now = datetime.now(UTC)
        payload = request.normalized_payload or request.request_payload or {}
        mock_execution = payload.get("mock_execution", {}) if isinstance(payload, dict) else {}
        gurux_operation = _map_profile_read_operation_to_gurux_definition(
            request.operation
        )
        validated_target = _validate_gurux_capture_load_profile_target(
            request,
            gurux_operation,
        )
        normalized_request = _normalize_gurux_capture_load_profile_request(
            request,
            validated_target,
        )
        invocation_request = _build_gurux_capture_load_profile_invocation_request(
            normalized_request
        )
        live_execution = _execute_live_tcp_profile_read_if_available(
            request,
            normalized_request=normalized_request,
            invocation_request=invocation_request,
        )
        trace_references = request.trace_references
        interval_count = len(validated_target.expected_profile_batch.load_profile_intervals)
        if live_execution is not None:
            return _build_runtime_profile_read_execution_from_live_tcp(
                request=request,
                now=now,
                gurux_operation=gurux_operation,
                validated_target=validated_target,
                normalized_request=normalized_request,
                invocation_request=invocation_request,
                live_execution=live_execution,
                interval_count=interval_count,
                trace_references=trace_references,
            )
        invocation_response = _invoke_gurux_capture_load_profile_stub(
            invocation_request,
            mock_execution=mock_execution,
        )
        requested_outcome = RuntimeCommandOutcome(
            mock_execution.get("outcome", RuntimeCommandOutcome.SUCCEEDED.value)
        )
        error_detail = mock_execution.get("error_detail") or mock_execution.get("error_message")
        interpreted_result = _interpret_gurux_capture_load_profile_response(
            invocation_response,
            requested_outcome=requested_outcome,
            error_detail=error_detail,
        )
        return RuntimeProfileReadExecutionResult(
            status=RuntimeProfileReadExecutionStatus.COMPLETED,
            profile_read_execution_record_id=(
                "runtime-profile-read:"
                f"{request.execution_context.command_attempt_id}:{request.execution_context.request_id or request.execution_context.command_id}"
            ),
            session_identifier=str(trace_references["session_identifier"]),
            dispatch_envelope_record_id=request.dispatch_envelope_record_id,
            delivery_contract_record_id=str(trace_references["delivery_contract_record_id"]),
            envelope_record_id=str(trace_references["envelope_record_id"]),
            publication_contract_record_id=str(
                trace_references["publication_contract_record_id"]
            ),
            attestation_record_id=str(trace_references["attestation_record_id"]),
            settlement_record_id=str(trace_references["settlement_record_id"]),
            reconciliation_record_id=str(trace_references["reconciliation_record_id"]),
            interpretation_record_id=str(trace_references["interpretation_record_id"]),
            observation_record_id=str(trace_references["observation_record_id"]),
            invocation_result_record_id=str(
                trace_references["invocation_result_record_id"]
            ),
            dispatch_request_record_id=str(trace_references["dispatch_request_record_id"]),
            selection_record_id=str(trace_references["selection_record_id"]),
            intent_record_id=str(trace_references["intent_record_id"]),
            closure_record_id=str(trace_references["closure_record_id"]),
            materialization_record_id=str(trace_references["materialization_record_id"]),
            post_processing_record_id=str(trace_references["post_processing_record_id"]),
            disposition_record_id=str(trace_references["disposition_record_id"]),
            outcome_record_id=str(trace_references["outcome_record_id"]),
            executor_identifier=str(request.execution_context.worker_identifier),
            job_run_id=str(request.execution_context.job_run_id),
            related_command_id=str(request.execution_context.command_id),
            command_attempt_id=str(request.execution_context.command_attempt_id),
            adapter_key=self.adapter_key,
            protocol_family=request.protocol_family,
            profile_read_operation=request.operation,
            command_category=request.command_category,
            adapter_acknowledgment_state=interpreted_result.adapter_acknowledgment_state,
            protocol_stage_outcome=interpreted_result.protocol_stage_outcome,
            execution_outcome=interpreted_result.execution_outcome,
            correlation_id=request.execution_context.correlation_id,
            request_id=request.execution_context.request_id,
            execution_started_at=now.isoformat(),
            execution_finished_at=now.isoformat(),
            profile_read_batch=interpreted_result.profile_read_batch,
            adapter_result_summary={
                "adapter_key": self.adapter_key,
                "operation": request.operation.value,
                "protocol_family": request.protocol_family.value,
                "adapter_acknowledged": invocation_response.acknowledged,
                "vertical_slice": "profile_read",
                "load_profile_interval_count": interval_count,
                "gurux_profile_read_operation": gurux_operation.model_dump(mode="json"),
                "gurux_profile_read_validated_target": validated_target.model_dump(
                    mode="json"
                ),
                "gurux_profile_read_normalized_request": normalized_request.model_dump(
                    mode="json"
                ),
                "gurux_profile_read_invocation_result": invocation_response.model_dump(
                    mode="json"
                ),
                "gurux_profile_read_interpreter": interpreted_result.model_dump(
                    mode="json"
                ),
            },
            adapter_response_snapshot={
                "adapter": self.adapter_key,
                "operation": request.operation.value,
                "target_meter_id": str(request.target.meter_id),
                "endpoint_id": str(request.target.endpoint_id),
                "protocol_profile_id": str(request.target.protocol_association_profile_id),
                "load_profile_interval_count": interval_count,
                "gurux_profile_read_operation": gurux_operation.model_dump(mode="json"),
                "gurux_profile_read_validated_target": validated_target.model_dump(
                    mode="json"
                ),
                "gurux_profile_read_normalized_request": normalized_request.model_dump(
                    mode="json"
                ),
                "gurux_profile_read_invocation_request": invocation_request.model_dump(
                    mode="json"
                ),
                "gurux_profile_read_invocation_result": invocation_response.model_dump(
                    mode="json"
                ),
                "gurux_profile_read_interpreter": interpreted_result.model_dump(
                    mode="json"
                ),
            },
            error_category=interpreted_result.error_category,
            error_detail=interpreted_result.error_detail,
            profile_read_recorded_by_executor_identifier=str(
                request.execution_context.worker_identifier
            ),
            already_recorded=False,
            summary=interpreted_result.interpreter_summary,
            lineage=request.lineage,
        )


def _execute_live_tcp_on_demand_read_if_available(
    request: RuntimeOnDemandReadAdapterRequest,
) -> LiveTcpOnDemandReadExecution | None:
    if request.transport.endpoint_transport_type != ConnectivityTransportType.TCP_IP:
        return None

    with borrow_runtime_tcp_meter_ingress_connection(
        meter_id=request.target.meter_id,
        endpoint_id=request.target.endpoint_id,
    ) as borrowed_connection:
        if borrowed_connection is None:
            return None

        config = _build_live_tcp_dlms_session_config(request)
        obis_codes = _resolve_on_demand_read_obis_codes(request)
        try:
            return execute_billing_snapshot_over_tcp_ingress(
                sock=borrowed_connection.socket,
                config=config,
                obis_codes=obis_codes,
            )
        except Exception:
            mark_runtime_tcp_meter_ingress_connection_dead(borrowed_connection.connection_id)
            raise


def _execute_live_tcp_profile_read_if_available(
    request: RuntimeProfileReadAdapterRequest,
    *,
    normalized_request: GuruxProfileReadNormalizedRequest,
    invocation_request: GuruxProfileReadInvocationRequest,
) -> LiveTcpProfileReadExecution | None:
    if request.transport.endpoint_transport_type != ConnectivityTransportType.TCP_IP:
        return None

    ingress_status = get_runtime_tcp_meter_ingress_status()
    target_is_currently_bound = (
        ingress_status.connected
        and ingress_status.bound_meter_id == request.target.meter_id
        and ingress_status.bound_endpoint_id == request.target.endpoint_id
    )
    with borrow_runtime_tcp_meter_ingress_connection(
        meter_id=request.target.meter_id,
        endpoint_id=request.target.endpoint_id,
    ) as borrowed_connection:
        if borrowed_connection is None:
            if target_is_currently_bound:
                return LiveTcpProfileReadExecution(
                    invocation_status="failed",
                    profile_read_batch_payload=None,
                    error_detail=(
                        "Bound live TCP ingress connection matched the target meter, "
                        "but profile-read could not borrow it for real execution."
                    ),
                    protocol_trace={
                        "used_bound_connection": False,
                        "expected_bound_connection": True,
                        "bound_meter_id": (
                            str(ingress_status.bound_meter_id)
                            if ingress_status.bound_meter_id is not None
                            else None
                        ),
                        "bound_endpoint_id": (
                            str(ingress_status.bound_endpoint_id)
                            if ingress_status.bound_endpoint_id is not None
                            else None
                        ),
                        "connection_in_use": ingress_status.connection_in_use,
                    },
                    raw_frames=[],
                    bytes_sent=0,
                    bytes_received=0,
                )
            return None

        capture_load_profile = (
            request.normalized_payload or request.request_payload or {}
        ).get("capture_load_profile", {})
        channels = (
            capture_load_profile.get("channels", [])
            if isinstance(capture_load_profile, dict)
            else []
        )
        try:
            return execute_capture_load_profile_over_tcp_ingress(
                sock=borrowed_connection.socket,
                config=_build_live_tcp_dlms_session_config(request),
                profile_obis_code=invocation_request.profile_obis_code,
                interval_start=min(
                    interval.interval_start
                    for interval in normalized_request.expected_profile_batch.load_profile_intervals
                ),
                interval_end=max(
                    interval.interval_end
                    for interval in normalized_request.expected_profile_batch.load_profile_intervals
                ),
                channels=[
                    item for item in channels if isinstance(item, dict)
                ],
            )
        except Exception:
            mark_runtime_tcp_meter_ingress_connection_dead(borrowed_connection.connection_id)
            raise


def _build_runtime_profile_read_execution_from_live_tcp(
    *,
    request: RuntimeProfileReadAdapterRequest,
    now: datetime,
    gurux_operation: GuruxProfileReadOperationDefinition,
    validated_target: GuruxProfileReadValidatedTarget,
    normalized_request: GuruxProfileReadNormalizedRequest,
    invocation_request: GuruxProfileReadInvocationRequest,
    live_execution: LiveTcpProfileReadExecution,
    interval_count: int,
    trace_references: dict[str, object],
) -> RuntimeProfileReadExecutionResult:
    if live_execution.invocation_status == "accepted":
        adapter_acknowledgment_state = RuntimeProfileReadAdapterAcknowledgmentState.ACCEPTED
        protocol_stage_outcome = RuntimeProfileReadProtocolStageOutcome.PROFILE_READ_COMPLETED
        execution_outcome = RuntimeCommandOutcome.SUCCEEDED
        error_category = None
    elif live_execution.invocation_status == "rejected":
        adapter_acknowledgment_state = RuntimeProfileReadAdapterAcknowledgmentState.REJECTED
        protocol_stage_outcome = RuntimeProfileReadProtocolStageOutcome.PROFILE_READ_FAILED
        execution_outcome = RuntimeCommandOutcome.FAILED
        error_category = RuntimeProfileReadErrorCategory.ADAPTER_REJECTED
    else:
        adapter_acknowledgment_state = RuntimeProfileReadAdapterAcknowledgmentState.ACCEPTED
        protocol_stage_outcome = RuntimeProfileReadProtocolStageOutcome.PROFILE_READ_FAILED
        execution_outcome = RuntimeCommandOutcome.FAILED
        error_category = RuntimeProfileReadErrorCategory.EXECUTION_FAILED

    profile_read_batch = (
        RuntimeReadingBatchPayload.model_validate(live_execution.profile_read_batch_payload)
        if isinstance(live_execution.profile_read_batch_payload, dict)
        else None
    )
    interpreter_summary = (
        "Live TCP ingress capture-load-profile execution completed over the bound session."
        if execution_outcome == RuntimeCommandOutcome.SUCCEEDED
        else (
            live_execution.error_detail
            or "Live TCP ingress capture-load-profile execution failed over the bound session."
        )
    )
    invocation_response = {
        "acknowledged": adapter_acknowledgment_state
        == RuntimeProfileReadAdapterAcknowledgmentState.ACCEPTED,
        "adapter_available": True,
        "invocation_status": live_execution.invocation_status,
        "profile_obis_code": invocation_request.profile_obis_code,
        "selector_name": invocation_request.selector_name,
        "selector_id": invocation_request.selector_id,
        "requested_channel_ids": invocation_request.requested_channel_ids,
        "requested_interval_count": invocation_request.requested_interval_count,
        "payload_snapshot": live_execution.profile_read_batch_payload,
        "error_detail": live_execution.error_detail,
    }
    interpreter = {
        "adapter_acknowledgment_state": adapter_acknowledgment_state.value,
        "protocol_stage_outcome": protocol_stage_outcome.value,
        "execution_outcome": execution_outcome.value,
        "profile_read_batch": (
            profile_read_batch.model_dump(mode="json") if profile_read_batch is not None else None
        ),
        "error_category": error_category.value if error_category is not None else None,
        "error_detail": live_execution.error_detail,
        "interpreter_summary": interpreter_summary,
    }
    return RuntimeProfileReadExecutionResult(
        status=RuntimeProfileReadExecutionStatus.COMPLETED,
        profile_read_execution_record_id=(
            "runtime-profile-read:"
            f"{request.execution_context.command_attempt_id}:{request.execution_context.request_id or request.execution_context.command_id}"
        ),
        session_identifier=str(trace_references["session_identifier"]),
        dispatch_envelope_record_id=request.dispatch_envelope_record_id,
        delivery_contract_record_id=str(trace_references["delivery_contract_record_id"]),
        envelope_record_id=str(trace_references["envelope_record_id"]),
        publication_contract_record_id=str(trace_references["publication_contract_record_id"]),
        attestation_record_id=str(trace_references["attestation_record_id"]),
        settlement_record_id=str(trace_references["settlement_record_id"]),
        reconciliation_record_id=str(trace_references["reconciliation_record_id"]),
        interpretation_record_id=str(trace_references["interpretation_record_id"]),
        observation_record_id=str(trace_references["observation_record_id"]),
        invocation_result_record_id=str(trace_references["invocation_result_record_id"]),
        dispatch_request_record_id=str(trace_references["dispatch_request_record_id"]),
        selection_record_id=str(trace_references["selection_record_id"]),
        intent_record_id=str(trace_references["intent_record_id"]),
        closure_record_id=str(trace_references["closure_record_id"]),
        materialization_record_id=str(trace_references["materialization_record_id"]),
        post_processing_record_id=str(trace_references["post_processing_record_id"]),
        disposition_record_id=str(trace_references["disposition_record_id"]),
        outcome_record_id=str(trace_references["outcome_record_id"]),
        executor_identifier=str(request.execution_context.worker_identifier),
        job_run_id=str(request.execution_context.job_run_id),
        related_command_id=str(request.execution_context.command_id),
        command_attempt_id=str(request.execution_context.command_attempt_id),
        adapter_key="gurux-dlms-bridge",
        protocol_family=request.protocol_family,
        profile_read_operation=request.operation,
        command_category=request.command_category,
        adapter_acknowledgment_state=adapter_acknowledgment_state,
        protocol_stage_outcome=protocol_stage_outcome,
        execution_outcome=execution_outcome,
        correlation_id=request.execution_context.correlation_id,
        request_id=request.execution_context.request_id,
        execution_started_at=now.isoformat(),
        execution_finished_at=now.isoformat(),
        profile_read_batch=profile_read_batch,
        adapter_result_summary={
            "adapter_key": "gurux-dlms-bridge",
            "operation": request.operation.value,
            "protocol_family": request.protocol_family.value,
            "adapter_acknowledged": (
                adapter_acknowledgment_state == RuntimeProfileReadAdapterAcknowledgmentState.ACCEPTED
            ),
            "vertical_slice": "profile_read",
            "load_profile_interval_count": interval_count,
            "live_tcp_ingress": True,
            "bytes_sent": live_execution.bytes_sent,
            "bytes_received": live_execution.bytes_received,
            "live_tcp_protocol_trace": live_execution.protocol_trace,
            "gurux_profile_read_operation": gurux_operation.model_dump(mode="json"),
            "gurux_profile_read_validated_target": validated_target.model_dump(mode="json"),
            "gurux_profile_read_normalized_request": normalized_request.model_dump(mode="json"),
            "gurux_profile_read_invocation_result": invocation_response,
            "gurux_profile_read_interpreter": interpreter,
        },
        adapter_response_snapshot={
            "adapter": "gurux-dlms-bridge",
            "operation": request.operation.value,
            "target_meter_id": str(request.target.meter_id),
            "endpoint_id": str(request.target.endpoint_id),
            "protocol_profile_id": str(request.target.protocol_association_profile_id),
            "load_profile_interval_count": interval_count,
            "live_tcp_ingress": True,
            "bytes_sent": live_execution.bytes_sent,
            "bytes_received": live_execution.bytes_received,
            "live_tcp_protocol_trace": live_execution.protocol_trace,
            "gurux_profile_read_operation": gurux_operation.model_dump(mode="json"),
            "gurux_profile_read_validated_target": validated_target.model_dump(mode="json"),
            "gurux_profile_read_normalized_request": normalized_request.model_dump(mode="json"),
            "gurux_profile_read_invocation_request": invocation_request.model_dump(mode="json"),
            "gurux_profile_read_invocation_result": invocation_response,
            "gurux_profile_read_interpreter": interpreter,
        },
        error_category=error_category,
        error_detail=live_execution.error_detail,
        profile_read_recorded_by_executor_identifier=str(
            request.execution_context.worker_identifier
        ),
        already_recorded=False,
        summary=interpreter_summary,
        lineage=request.lineage,
    )


def _execute_live_tcp_relay_control_if_available(
    request: RuntimeRelayControlAdapterRequest,
    *,
    gurux_operation: GuruxRelayControlOperationDefinition,
) -> LiveTcpRelayControlExecution | None:
    if request.transport.endpoint_transport_type != ConnectivityTransportType.TCP_IP:
        return None

    ingress_status = get_runtime_tcp_meter_ingress_status()
    target_is_currently_bound = (
        ingress_status.connected
        and ingress_status.bound_meter_id == request.target.meter_id
        and ingress_status.bound_endpoint_id == request.target.endpoint_id
    )
    with borrow_runtime_tcp_meter_ingress_connection(
        meter_id=request.target.meter_id,
        endpoint_id=request.target.endpoint_id,
    ) as borrowed_connection:
        if borrowed_connection is None:
            if target_is_currently_bound:
                return LiveTcpRelayControlExecution(
                    invocation_status="failed",
                    before_state=None,
                    after_state=None,
                    error_detail=(
                        "Bound live TCP ingress connection matched the target meter, "
                        "but relay-control could not borrow it for real execution."
                    ),
                    protocol_trace={
                        "used_bound_connection": False,
                        "expected_bound_connection": True,
                        "bound_meter_id": (
                            str(ingress_status.bound_meter_id)
                            if ingress_status.bound_meter_id is not None
                            else None
                        ),
                        "bound_endpoint_id": (
                            str(ingress_status.bound_endpoint_id)
                            if ingress_status.bound_endpoint_id is not None
                            else None
                        ),
                        "connection_in_use": ingress_status.connection_in_use,
                    },
                    raw_frames=[],
                    bytes_sent=0,
                    bytes_received=0,
                )
            return None

        try:
            return execute_relay_control_over_tcp_ingress(
                sock=borrowed_connection.socket,
                config=_build_live_tcp_dlms_session_config(request),
                relay_obis_code=gurux_operation.obis_code,
                operation_name=gurux_operation.method_name,
            )
        except Exception:
            mark_runtime_tcp_meter_ingress_connection_dead(borrowed_connection.connection_id)
            raise


def _build_live_tcp_dlms_session_config(
    request: RuntimeOnDemandReadAdapterRequest | RuntimeRelayControlAdapterRequest,
) -> LiveTcpDlmsSessionConfig:
    protocol_settings = request.protocol_settings or {}
    start_protocol = _resolve_live_tcp_start_protocol(request)
    password = resolve_runtime_secret_ref(request.security.password_secret_ref)
    if request.security.authentication_mode.value == "low" and password is None:
        raise RuntimeError(
            "Live TCP ingress requires a resolvable password secret for LOW authentication."
        )
    if request.client_address is None or request.server_address is None:
        raise RuntimeError(
            "Live TCP ingress requires client and server addresses for DLMS association."
        )

    def _int_setting(key: str, default: int) -> int:
        return int(protocol_settings.get(key, default))

    def _float_setting(key: str, default: float) -> float:
        return float(protocol_settings.get(key, default))

    def _bool_setting(key: str, default: bool) -> bool:
        value = protocol_settings.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    ack_candidates_raw = protocol_settings.get("iec_ack_hex_candidates")
    ack_candidates = (
        [str(item) for item in ack_candidates_raw if str(item).strip()]
        if isinstance(ack_candidates_raw, list)
        else ["063235320D0A", "06B235B28D0A"]
    )

    return LiveTcpDlmsSessionConfig(
        start_protocol=start_protocol,  # type: ignore[arg-type]
        client_address=request.client_address,
        server_address=request.server_address,
        server_address_size=request.server_address_size,
        authentication_mode=request.security.authentication_mode.value,
        password=password,
        iec_ack_hex_candidates=ack_candidates,
        use_broadcast_snrm_first=_bool_setting("use_broadcast_snrm_first", True),
        broadcast_snrm_hex=str(
            protocol_settings.get("broadcast_snrm_hex", "7EA00AFEFEFEFF0393C9837E")
        ),
        after_iec_sleep_ms=_int_setting("after_iec_sleep_ms", 1200),
        dlms_read_timeout_seconds=_float_setting("dlms_read_timeout_seconds", 2.5),
        iec_serial_timeout_seconds=_float_setting("iec_serial_timeout_seconds", 5.0),
        iec_wake_zero_bytes=_int_setting("iec_wake_zero_bytes", 0),
        iec_wake_post_delay_ms=_int_setting("iec_wake_post_delay_ms", 0),
        iec_ident_retries=_int_setting("iec_ident_retries", 4),
        iec_ident_retry_delay_ms=_int_setting("iec_ident_retry_delay_ms", 350),
        before_first_iec_send_delay_ms=settings.runtime_tcp_meter_ingress_before_first_iec_send_delay_ms,
        ua_swap_addresses=_bool_setting("ua_swap_addresses", False),
        send_hdlc_disc_before_close=_bool_setting("send_hdlc_disc_before_close", True),
        disc_drain_timeout_seconds=_float_setting("disc_drain_timeout_seconds", 0.4),
    )


def _resolve_live_tcp_start_protocol(
    request: RuntimeOnDemandReadAdapterRequest | RuntimeRelayControlAdapterRequest,
) -> str:
    protocol_settings = request.protocol_settings or {}
    configured = protocol_settings.get("tcp_start_protocol")
    if isinstance(configured, str):
        normalized = configured.strip().lower()
        if normalized in {"iec", "iec62056_21", "iec62056-21"}:
            return "iec62056_21"
        if normalized in {"dlms", "hdlc", "snrm"}:
            return "dlms"
    return "iec62056_21" if request.iec62056_21_enabled else "dlms"


def _resolve_on_demand_read_obis_codes(
    request: RuntimeOnDemandReadAdapterRequest,
) -> list[str]:
    payload = request.normalized_payload or request.request_payload or {}
    explicit_obis = payload.get("obis") if isinstance(payload, dict) else None
    if isinstance(explicit_obis, list):
        normalized = [str(item).strip() for item in explicit_obis if str(item).strip()]
        if normalized:
            return normalized
    return ["1.0.1.8.0.255", "1.0.2.8.0.255"]


class GuruxProfileReadOperationDefinition(BaseModel):
    operation: RuntimeProfileReadOperation
    interface_class: str
    class_id: int
    obis_code: str
    selector_name: str
    selector_id: int
    capture_object_type: str


class GuruxProfileReadValidatedTarget(BaseModel):
    gurux_operation: GuruxProfileReadOperationDefinition
    target_object: dict[str, object]
    endpoint_identity: dict[str, object]
    protocol_profile: dict[str, object]
    transport_prerequisites_present: bool
    security_prerequisites_present: bool
    requested_channel_ids: list[str]
    requested_interval_count: int
    expected_profile_batch: RuntimeReadingBatchPayload
    trace_references: dict[str, object]


class GuruxProfileReadNormalizedRequest(BaseModel):
    adapter_key: str
    command_attempt_id: str
    dispatch_envelope_record_id: str
    gurux_operation: GuruxProfileReadOperationDefinition
    target_object: dict[str, object]
    endpoint_identity: dict[str, object]
    protocol_profile: dict[str, object]
    transport_context: dict[str, object]
    security_context: dict[str, object]
    invocation_context: dict[str, object]
    requested_channel_ids: list[str]
    expected_profile_batch: RuntimeReadingBatchPayload
    trace_references: dict[str, object]


class GuruxProfileReadInvocationRequest(BaseModel):
    adapter_key: str
    command_attempt_id: str
    dispatch_envelope_record_id: str
    correlation_id: str | None = None
    request_id: str | None = None
    target_meter_id: str
    endpoint_id: str
    protocol_profile_id: str
    transport_type: str
    transport_locator: str
    port: int | None = None
    authentication_mode: str
    password_secret_ref: str | None = None
    profile_obis_code: str
    selector_name: str
    selector_id: int
    requested_channel_ids: list[str]
    requested_interval_count: int


class GuruxProfileReadInvocationResponse(BaseModel):
    acknowledged: bool
    adapter_available: bool
    invocation_status: str
    profile_obis_code: str
    payload_snapshot: dict[str, object] | None = None
    response_received_at: str
    error_detail: str | None = None


class GuruxProfileReadInterpretedResult(BaseModel):
    adapter_acknowledgment_state: RuntimeProfileReadAdapterAcknowledgmentState
    protocol_stage_outcome: RuntimeProfileReadProtocolStageOutcome
    execution_outcome: RuntimeCommandOutcome
    profile_read_batch: RuntimeReadingBatchPayload | None = None
    error_category: RuntimeProfileReadErrorCategory | None = None
    error_detail: str | None = None
    interpreter_summary: str


class GuruxRelayControlOperationDefinition(BaseModel):
    operation: RuntimeRelayControlOperation
    interface_class: str
    class_id: int
    obis_code: str
    method_name: str
    method_index: int


class GuruxRelayControlValidatedTarget(BaseModel):
    gurux_operation: GuruxRelayControlOperationDefinition
    target_object: dict[str, object]
    endpoint_identity: dict[str, object]
    protocol_profile: dict[str, object]
    transport_prerequisites_present: bool
    security_prerequisites_present: bool
    trace_references: dict[str, object]


class GuruxRelayControlResolvedTransportProfile(BaseModel):
    gurux_operation: GuruxRelayControlOperationDefinition
    endpoint_identity: dict[str, object]
    transport_profile: dict[str, object]
    protocol_profile: dict[str, object]
    security_profile: dict[str, object]
    trace_references: dict[str, object]


class GuruxRelayControlNormalizedRequest(BaseModel):
    adapter_key: str
    command_attempt_id: str
    dispatch_envelope_record_id: str
    gurux_operation: GuruxRelayControlOperationDefinition
    target_object: dict[str, object]
    transport_context: dict[str, object]
    security_context: dict[str, object]
    invocation_context: dict[str, object]
    trace_references: dict[str, object]


class GuruxRelayControlInvocationStubRequest(BaseModel):
    adapter_key: str
    command_attempt_id: str
    dispatch_envelope_record_id: str
    correlation_id: str | None = None
    request_id: str | None = None
    target_meter_id: str
    endpoint_id: str
    protocol_profile_id: str
    transport_type: str
    transport_locator: str
    port: int | None = None
    authentication_mode: str
    password_secret_ref: str | None = None
    operation: GuruxRelayControlOperationDefinition


class GuruxRelayControlInvocationStubResponse(BaseModel):
    transport_adapter: str
    invocation_status: str
    acknowledged: bool
    invocation_reference: str
    request_shape: dict[str, object]
    response_shape: dict[str, object]


class GuruxRelayControlInterpretedResult(BaseModel):
    invocation_status: str
    adapter_acknowledgment_state: RuntimeRelayControlAdapterAcknowledgmentState
    protocol_stage_outcome: RuntimeRelayControlProtocolStageOutcome
    execution_outcome: RuntimeCommandOutcome
    error_category: RuntimeRelayControlErrorCategory | None = None
    error_detail: str | None = None
    interpreter_summary: str


class GuruxRelayControlExecutionAuditSummary(BaseModel):
    gurux_feature_flag_enabled: bool
    gurux_path_selected: bool
    relay_operation: str | None = None
    gurux_method_name: str | None = None
    resolved_transport_profile_present: bool
    validated_target_present: bool
    normalized_request_present: bool
    invocation_attempted: bool
    interpreted_result_present: bool
    resolved_transport_locator: str | None = None
    resolved_protocol_profile_id: str | None = None
    transport_prerequisites_present: bool | None = None
    security_prerequisites_present: bool | None = None
    terminal_invocation_status: str | None = None
    terminal_execution_outcome: RuntimeCommandOutcome | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    session_identifier: str | None = None
    stopped_at_stage: str | None = None


class GuruxRelayControlExecutionPhaseProgression(BaseModel):
    gurux_feature_flag_enabled: bool
    gurux_path_selected: bool
    relay_operation: str | None = None
    resolver_stage_state: str
    validator_stage_state: str
    normalizer_stage_state: str
    invocation_stage_state: str
    interpreter_stage_state: str
    stopped_at_stage: str | None = None
    terminal_invocation_status: str | None = None
    terminal_execution_outcome: RuntimeCommandOutcome | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    session_identifier: str | None = None


class GuruxRelayControlTerminalAdapterStatus(BaseModel):
    gurux_feature_flag_enabled: bool
    gurux_path_selected: bool
    relay_operation: str | None = None
    adapter_terminal_state: str
    terminal_acknowledgment_class: str | None = None
    final_execution_disposition: RuntimeCommandOutcome | None = None
    terminal_invocation_status: str | None = None
    stopped_at_stage: str | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    session_identifier: str | None = None


def _map_profile_read_operation_to_gurux_definition(
    operation: RuntimeProfileReadOperation | str,
) -> GuruxProfileReadOperationDefinition:
    normalized = operation.value if isinstance(operation, RuntimeProfileReadOperation) else str(operation)
    if normalized == RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE.value:
        return GuruxProfileReadOperationDefinition(
            operation=RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE,
            interface_class="profile_generic",
            class_id=7,
            obis_code="1.0.99.1.0.255",
            selector_name="capture_period_range",
            selector_id=1,
            capture_object_type="load_profile",
        )
    raise ValueError(
        f"Unsupported profile-read operation '{normalized}' for the Gurux profile-read mapper."
    )


def _validate_gurux_capture_load_profile_target(
    request: RuntimeProfileReadAdapterRequest,
    gurux_operation: GuruxProfileReadOperationDefinition,
) -> GuruxProfileReadValidatedTarget:
    if request.operation != RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE:
        raise ValueError(
            "Runtime profile read validator only supports the capture-load-profile operation."
        )

    payload = request.normalized_payload or request.request_payload or {}
    mock_execution = payload.get("mock_execution", {}) if isinstance(payload, dict) else {}
    explicit_reading_batch = (
        mock_execution.get("reading_batch") if isinstance(mock_execution, dict) else None
    )
    capture_load_profile_payload = (
        payload.get("capture_load_profile") if isinstance(payload, dict) else None
    )
    if isinstance(explicit_reading_batch, dict):
        expected_profile_batch = RuntimeReadingBatchPayload.model_validate(explicit_reading_batch)
    elif isinstance(capture_load_profile_payload, dict):
        interval_start = capture_load_profile_payload.get("interval_start")
        interval_end = capture_load_profile_payload.get("interval_end")
        channel_ids = capture_load_profile_payload.get("channel_ids")
        if (
            not isinstance(interval_start, str)
            or not isinstance(interval_end, str)
            or not isinstance(channel_ids, list)
            or not channel_ids
        ):
            raise ValueError(
                "Missing adapter prerequisites for the profile-read capture-load-profile validator."
            )
        try:
            normalized_interval_start = datetime.fromisoformat(interval_start)
            normalized_interval_end = datetime.fromisoformat(interval_end)
            normalized_channel_ids = [str(channel_id) for channel_id in channel_ids]
        except ValueError as exc:
            raise ValueError(
                "Missing adapter prerequisites for the profile-read capture-load-profile validator."
            ) from exc
        expected_profile_batch = RuntimeReadingBatchPayload(
            source_type=ReadingSourceType.COMMAND_RESULT,
            captured_at=normalized_interval_start,
            received_at=normalized_interval_end,
            status=ReadingBatchStatus.RECEIVED,
            correlation_id=request.execution_context.correlation_id,
            reading_context={
                "adapter_key": request.adapter_key,
                "vertical_slice": "profile_read",
                "operation": request.operation.value,
            },
            load_profile_intervals=[
                RuntimeLoadProfileIntervalPayload(
                    channel_id=channel_id,
                    interval_start=normalized_interval_start,
                    interval_end=normalized_interval_end,
                )
                for channel_id in normalized_channel_ids
            ],
        )
    else:
        raise ValueError(
            "Missing adapter prerequisites for the profile-read capture-load-profile validator."
        )
    if not expected_profile_batch.load_profile_intervals:
        raise ValueError(
            "Missing adapter prerequisites for the profile-read capture-load-profile validator."
        )

    transport_locator = request.transport.host or request.transport.ip_address
    transport_prerequisites_present = (
        request.transport.endpoint_transport_type is not None and transport_locator is not None
    )
    security_prerequisites_present = request.security.authentication_mode is not None
    if not transport_prerequisites_present or not security_prerequisites_present:
        raise ValueError(
            "Missing adapter prerequisites for the profile-read capture-load-profile validator."
        )

    requested_channel_ids = sorted(
        {str(interval.channel_id) for interval in expected_profile_batch.load_profile_intervals}
    )
    interval_start = min(
        interval.interval_start for interval in expected_profile_batch.load_profile_intervals
    )
    interval_end = max(
        interval.interval_end for interval in expected_profile_batch.load_profile_intervals
    )
    return GuruxProfileReadValidatedTarget(
        gurux_operation=gurux_operation,
        target_object={
            "interface_class": gurux_operation.interface_class,
            "class_id": gurux_operation.class_id,
            "obis_code": gurux_operation.obis_code,
            "selector_name": gurux_operation.selector_name,
            "selector_id": gurux_operation.selector_id,
            "requested_window_start": interval_start.isoformat(),
            "requested_window_end": interval_end.isoformat(),
            "capture_object_type": gurux_operation.capture_object_type,
        },
        endpoint_identity={
            "meter_id": str(request.target.meter_id),
            "meter_serial_number": request.target.serial_number,
            "endpoint_id": str(request.target.endpoint_id),
            "endpoint_code": request.target.endpoint_code,
        },
        protocol_profile={
            "protocol_profile_id": str(request.target.protocol_association_profile_id),
            "protocol_family": request.protocol_family.value,
        },
        transport_prerequisites_present=transport_prerequisites_present,
        security_prerequisites_present=security_prerequisites_present,
        requested_channel_ids=requested_channel_ids,
        requested_interval_count=len(expected_profile_batch.load_profile_intervals),
        expected_profile_batch=expected_profile_batch,
        trace_references=request.trace_references,
    )


def _normalize_gurux_capture_load_profile_request(
    request: RuntimeProfileReadAdapterRequest,
    validated_target: GuruxProfileReadValidatedTarget,
) -> GuruxProfileReadNormalizedRequest:
    transport_locator = request.transport.host or request.transport.ip_address
    if transport_locator is None:
        raise ValueError(
            "Missing adapter prerequisites for the profile-read capture-load-profile request shaper."
        )

    return GuruxProfileReadNormalizedRequest(
        adapter_key=request.adapter_key,
        command_attempt_id=str(request.execution_context.command_attempt_id),
        dispatch_envelope_record_id=request.dispatch_envelope_record_id,
        gurux_operation=validated_target.gurux_operation,
        target_object=validated_target.target_object,
        endpoint_identity=validated_target.endpoint_identity,
        protocol_profile=validated_target.protocol_profile,
        transport_context={
            "transport_type": request.transport.endpoint_transport_type.value,
            "transport_locator": transport_locator,
            "port": request.transport.port,
        },
        security_context={
            "authentication_mode": request.security.authentication_mode.value,
            "password_secret_ref": request.security.password_secret_ref,
            "security_suite": request.security.security_suite,
        },
        invocation_context={
            "correlation_id": request.execution_context.correlation_id,
            "request_id": request.execution_context.request_id,
            "requested_interval_count": validated_target.requested_interval_count,
            "requested_window_start": validated_target.target_object["requested_window_start"],
            "requested_window_end": validated_target.target_object["requested_window_end"],
        },
        requested_channel_ids=validated_target.requested_channel_ids,
        expected_profile_batch=validated_target.expected_profile_batch,
        trace_references=request.trace_references,
    )


def _build_gurux_capture_load_profile_invocation_request(
    normalized_request: GuruxProfileReadNormalizedRequest,
) -> GuruxProfileReadInvocationRequest:
    return GuruxProfileReadInvocationRequest(
        adapter_key=normalized_request.adapter_key,
        command_attempt_id=normalized_request.command_attempt_id,
        dispatch_envelope_record_id=normalized_request.dispatch_envelope_record_id,
        correlation_id=normalized_request.invocation_context.get("correlation_id"),
        request_id=normalized_request.invocation_context.get("request_id"),
        target_meter_id=str(normalized_request.endpoint_identity["meter_id"]),
        endpoint_id=str(normalized_request.endpoint_identity["endpoint_id"]),
        protocol_profile_id=str(
            normalized_request.protocol_profile["protocol_profile_id"]
        ),
        transport_type=str(normalized_request.transport_context["transport_type"]),
        transport_locator=str(normalized_request.transport_context["transport_locator"]),
        port=normalized_request.transport_context.get("port"),
        authentication_mode=str(normalized_request.security_context["authentication_mode"]),
        password_secret_ref=normalized_request.security_context.get("password_secret_ref"),
        profile_obis_code=str(normalized_request.target_object["obis_code"]),
        selector_name=str(normalized_request.target_object["selector_name"]),
        selector_id=int(normalized_request.target_object["selector_id"]),
        requested_channel_ids=normalized_request.requested_channel_ids,
        requested_interval_count=int(
            normalized_request.invocation_context["requested_interval_count"]
        ),
    )


def _invoke_gurux_capture_load_profile_stub(
    invocation_request: GuruxProfileReadInvocationRequest,
    *,
    mock_execution: dict[str, object],
) -> GuruxProfileReadInvocationResponse:
    adapter_available = bool(mock_execution.get("adapter_available", True))
    acknowledged = bool(mock_execution.get("adapter_acknowledged", True))
    if not adapter_available:
        invocation_status = "unavailable"
    elif acknowledged:
        invocation_status = "accepted"
    else:
        invocation_status = "rejected"

    payload_snapshot = (
        mock_execution.get("reading_batch")
        if isinstance(mock_execution.get("reading_batch"), dict)
        else None
    )
    if payload_snapshot is None and invocation_status == "accepted":
        payload_snapshot = {
            "source_type": "command_result",
            "captured_at": datetime.now(UTC).isoformat(),
            "received_at": datetime.now(UTC).isoformat(),
            "status": "received",
            "load_profile_intervals": [
                {
                    "channel_id": channel_id,
                    "interval_start": datetime.now(UTC).isoformat(),
                    "interval_end": datetime.now(UTC).isoformat(),
                }
                for channel_id in invocation_request.requested_channel_ids
            ],
        }
    return GuruxProfileReadInvocationResponse(
        acknowledged=acknowledged,
        adapter_available=adapter_available,
        invocation_status=invocation_status,
        profile_obis_code=invocation_request.profile_obis_code,
        payload_snapshot=payload_snapshot,
        response_received_at=datetime.now(UTC).isoformat(),
        error_detail=mock_execution.get("error_detail") or mock_execution.get("error_message"),
    )


def _interpret_gurux_capture_load_profile_response(
    invocation_response: GuruxProfileReadInvocationResponse,
    *,
    requested_outcome: RuntimeCommandOutcome,
    error_detail: str | None,
) -> GuruxProfileReadInterpretedResult:
    terminal_error_detail = error_detail or invocation_response.error_detail
    if not invocation_response.adapter_available:
        return GuruxProfileReadInterpretedResult(
            adapter_acknowledgment_state=RuntimeProfileReadAdapterAcknowledgmentState.REJECTED,
            protocol_stage_outcome=RuntimeProfileReadProtocolStageOutcome.PROFILE_READ_FAILED,
            execution_outcome=(
                requested_outcome
                if requested_outcome != RuntimeCommandOutcome.SUCCEEDED
                else RuntimeCommandOutcome.FAILED
            ),
            error_category=RuntimeProfileReadErrorCategory.EXECUTION_FAILED,
            error_detail=terminal_error_detail or "Profile-read adapter is unavailable.",
            interpreter_summary=(
                "Capture-load-profile interpretation refused the response because the "
                "bounded Gurux adapter path was unavailable."
            ),
        )
    if not invocation_response.acknowledged:
        return GuruxProfileReadInterpretedResult(
            adapter_acknowledgment_state=RuntimeProfileReadAdapterAcknowledgmentState.REJECTED,
            protocol_stage_outcome=RuntimeProfileReadProtocolStageOutcome.PROFILE_READ_FAILED,
            execution_outcome=(
                requested_outcome
                if requested_outcome != RuntimeCommandOutcome.SUCCEEDED
                else RuntimeCommandOutcome.FAILED
            ),
            error_category=RuntimeProfileReadErrorCategory.ADAPTER_REJECTED,
            error_detail=terminal_error_detail or "Profile-read adapter rejected the request.",
            interpreter_summary=(
                "Capture-load-profile interpretation mapped the Gurux invocation to a "
                "bounded rejected profile-read outcome."
            ),
        )
    if not isinstance(invocation_response.payload_snapshot, dict):
        raise ValueError(
            "Unusable adapter response shape for the profile-read capture-load-profile interpreter."
        )

    profile_read_batch = RuntimeReadingBatchPayload.model_validate(
        invocation_response.payload_snapshot
    )
    error_category = None
    if requested_outcome != RuntimeCommandOutcome.SUCCEEDED:
        error_category = RuntimeProfileReadErrorCategory.EXECUTION_FAILED
    return GuruxProfileReadInterpretedResult(
        adapter_acknowledgment_state=RuntimeProfileReadAdapterAcknowledgmentState.ACCEPTED,
        protocol_stage_outcome=(
            RuntimeProfileReadProtocolStageOutcome.PROFILE_READ_COMPLETED
            if requested_outcome == RuntimeCommandOutcome.SUCCEEDED
            else RuntimeProfileReadProtocolStageOutcome.PROFILE_READ_FAILED
        ),
        execution_outcome=requested_outcome,
        profile_read_batch=profile_read_batch,
        error_category=error_category,
        error_detail=terminal_error_detail,
        interpreter_summary=(
            "Capture-load-profile interpretation mapped the bounded Gurux response into "
            "the runtime-facing profile-read result contract."
        ),
    )


def _map_relay_control_operation_to_gurux_definition(
    operation: RuntimeRelayControlOperation | str,
) -> GuruxRelayControlOperationDefinition:
    if not settings.enable_runtime_relay_control_gurux_mapper:
        raise NotImplementedError(
            "Runtime relay-control Gurux mapper is disabled."
        )

    normalized = operation.value if isinstance(operation, RuntimeRelayControlOperation) else str(operation)
    if normalized == RuntimeRelayControlOperation.DISCONNECT.value:
        return GuruxRelayControlOperationDefinition(
            operation=RuntimeRelayControlOperation.DISCONNECT,
            interface_class="disconnect_control",
            class_id=70,
            obis_code="0.0.96.3.10.255",
            method_name="remote_disconnect",
            method_index=1,
        )
    if normalized == RuntimeRelayControlOperation.RECONNECT.value:
        return GuruxRelayControlOperationDefinition(
            operation=RuntimeRelayControlOperation.RECONNECT,
            interface_class="disconnect_control",
            class_id=70,
            obis_code="0.0.96.3.10.255",
            method_name="remote_reconnect",
            method_index=2,
        )
    raise ValueError(
        f"Unsupported relay operation '{normalized}' for the Gurux relay-control mapper."
    )


def _resolve_gurux_relay_control_transport_profile(
    request: RuntimeRelayControlAdapterRequest,
    operation: GuruxRelayControlOperationDefinition,
) -> GuruxRelayControlResolvedTransportProfile:
    if not settings.enable_runtime_relay_control_gurux_mapper:
        raise NotImplementedError(
            "Runtime relay-control Gurux mapper is disabled."
        )

    transport_locator = (
        request.transport.host
        or request.transport.ip_address
        or request.transport.serial_port_name
        or request.transport.gateway_identifier
    )
    if not request.target.endpoint_code or transport_locator is None:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux transport/profile resolver."
        )
    if request.transport.endpoint_transport_type is None:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux transport/profile resolver."
        )
    if request.target.protocol_association_profile_id is None:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux transport/profile resolver."
        )
    if request.security.authentication_mode is None:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux transport/profile resolver."
        )

    return GuruxRelayControlResolvedTransportProfile(
        gurux_operation=operation,
        endpoint_identity={
            "endpoint_id": str(request.target.endpoint_id),
            "endpoint_code": request.target.endpoint_code,
            "endpoint_assignment_id": str(request.target.endpoint_assignment_id),
        },
        transport_profile={
            "transport_type": request.transport.endpoint_transport_type.value,
            "transport_locator": transport_locator,
            "port": request.transport.port,
        },
        protocol_profile={
            "protocol_family": request.protocol_family.value,
            "protocol_profile_id": str(request.target.protocol_association_profile_id),
        },
        security_profile={
            "authentication_mode": request.security.authentication_mode.value,
            "password_secret_ref": request.security.password_secret_ref,
            "security_suite": request.security.security_suite,
        },
        trace_references={
            "dispatch_envelope_record_id": request.dispatch_envelope_record_id,
            **request.trace_references,
        },
    )


def _validate_gurux_relay_control_target_object(
    request: RuntimeRelayControlAdapterRequest,
    resolved_transport_profile: GuruxRelayControlResolvedTransportProfile,
) -> GuruxRelayControlValidatedTarget:
    if not settings.enable_runtime_relay_control_gurux_mapper:
        raise NotImplementedError(
            "Runtime relay-control Gurux mapper is disabled."
        )

    if not request.target.serial_number:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux target-object validator."
        )
    if not request.target.manufacturer_code or not request.target.meter_model_code:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux target-object validator."
        )

    transport_prerequisites_present = (
        resolved_transport_profile.transport_profile.get("transport_type") is not None
        and resolved_transport_profile.transport_profile.get("transport_locator") is not None
    )
    security_prerequisites_present = (
        resolved_transport_profile.security_profile.get("authentication_mode") is not None
    )
    if not transport_prerequisites_present or not security_prerequisites_present:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux target-object validator."
        )

    return GuruxRelayControlValidatedTarget(
        gurux_operation=resolved_transport_profile.gurux_operation,
        target_object={
            "meter_id": str(request.target.meter_id),
            "serial_number": request.target.serial_number,
            "manufacturer_code": request.target.manufacturer_code,
            "meter_model_code": request.target.meter_model_code,
        },
        endpoint_identity=resolved_transport_profile.endpoint_identity,
        protocol_profile=resolved_transport_profile.protocol_profile,
        transport_prerequisites_present=transport_prerequisites_present,
        security_prerequisites_present=security_prerequisites_present,
        trace_references=resolved_transport_profile.trace_references,
    )


def _normalize_gurux_relay_control_request(
    request: RuntimeRelayControlAdapterRequest,
    resolved_transport_profile: GuruxRelayControlResolvedTransportProfile,
    validated_target: GuruxRelayControlValidatedTarget,
) -> GuruxRelayControlNormalizedRequest:
    if not settings.enable_runtime_relay_control_gurux_mapper:
        raise NotImplementedError(
            "Runtime relay-control Gurux mapper is disabled."
        )

    transport_locator = resolved_transport_profile.transport_profile.get("transport_locator")
    if not transport_locator:
        raise ValueError(
            "Missing adapter prerequisites for the relay-control Gurux request normalizer."
        )

    return GuruxRelayControlNormalizedRequest(
        adapter_key=request.adapter_key,
        command_attempt_id=str(request.execution_context.command_attempt_id),
        dispatch_envelope_record_id=request.dispatch_envelope_record_id,
        gurux_operation=validated_target.gurux_operation,
        target_object={
            **validated_target.target_object,
            "endpoint_id": validated_target.endpoint_identity["endpoint_id"],
            "protocol_profile_id": validated_target.protocol_profile["protocol_profile_id"],
        },
        transport_context={
            "transport_type": resolved_transport_profile.transport_profile["transport_type"],
            "transport_locator": transport_locator,
            "port": resolved_transport_profile.transport_profile.get("port"),
            "transport_prerequisites_present": validated_target.transport_prerequisites_present,
        },
        security_context={
            "authentication_mode": resolved_transport_profile.security_profile["authentication_mode"],
            "password_secret_ref": resolved_transport_profile.security_profile.get(
                "password_secret_ref"
            ),
            "security_suite": resolved_transport_profile.security_profile.get(
                "security_suite"
            ),
            "security_prerequisites_present": validated_target.security_prerequisites_present,
        },
        invocation_context={
            "correlation_id": request.execution_context.correlation_id,
            "request_id": request.execution_context.request_id,
            "worker_identifier": request.execution_context.worker_identifier,
            "command_category": request.command_category.value,
            "relay_operation": request.operation.value,
        },
        trace_references=validated_target.trace_references,
    )


def _build_gurux_relay_control_invocation_stub_request(
    normalized_request: GuruxRelayControlNormalizedRequest,
) -> GuruxRelayControlInvocationStubRequest:
    return GuruxRelayControlInvocationStubRequest(
        adapter_key=normalized_request.adapter_key,
        command_attempt_id=normalized_request.command_attempt_id,
        dispatch_envelope_record_id=normalized_request.dispatch_envelope_record_id,
        correlation_id=normalized_request.invocation_context.get("correlation_id"),
        request_id=normalized_request.invocation_context.get("request_id"),
        target_meter_id=str(normalized_request.target_object["meter_id"]),
        endpoint_id=str(normalized_request.target_object["endpoint_id"]),
        protocol_profile_id=str(normalized_request.target_object["protocol_profile_id"]),
        transport_type=str(normalized_request.transport_context["transport_type"]),
        transport_locator=str(normalized_request.transport_context["transport_locator"]),
        port=(
            int(normalized_request.transport_context["port"])
            if normalized_request.transport_context.get("port") is not None
            else None
        ),
        authentication_mode=str(normalized_request.security_context["authentication_mode"]),
        password_secret_ref=(
            str(normalized_request.security_context["password_secret_ref"])
            if normalized_request.security_context.get("password_secret_ref") is not None
            else None
        ),
        operation=normalized_request.gurux_operation,
    )


def _invoke_gurux_relay_control_stub(
    request: GuruxRelayControlInvocationStubRequest,
    *,
    mock_execution: dict[str, object],
) -> GuruxRelayControlInvocationStubResponse:
    invocation_status = str(
        mock_execution.get(
            "invocation_status",
            "acknowledged" if bool(mock_execution.get("adapter_acknowledged", True)) else "rejected",
        )
    )
    acknowledged = invocation_status == "acknowledged"
    invocation_reference = (
        "gurux-relay-invocation:"
        f"{request.command_attempt_id}:{request.operation.method_name}"
    )
    return GuruxRelayControlInvocationStubResponse(
        transport_adapter="gurux_stub",
        invocation_status=invocation_status,
        acknowledged=acknowledged,
        invocation_reference=invocation_reference,
        request_shape={
            "interface_class": request.operation.interface_class,
            "class_id": request.operation.class_id,
            "obis_code": request.operation.obis_code,
            "method_name": request.operation.method_name,
            "method_index": request.operation.method_index,
            "transport_type": request.transport_type,
            "transport_locator": request.transport_locator,
            "port": request.port,
        },
        response_shape={
            "invocation_status": invocation_status,
            "invocation_reference": invocation_reference,
            "target_meter_id": request.target_meter_id,
            "acknowledged_path": acknowledged,
        },
    )


def _interpret_gurux_relay_control_stub_response(
    response: GuruxRelayControlInvocationStubResponse,
    *,
    requested_outcome: RuntimeCommandOutcome,
    error_detail: str | None,
) -> GuruxRelayControlInterpretedResult:
    if not settings.enable_runtime_relay_control_gurux_mapper:
        raise NotImplementedError(
            "Runtime relay-control Gurux mapper is disabled."
        )

    if response.invocation_status == "acknowledged":
        return GuruxRelayControlInterpretedResult(
            invocation_status=response.invocation_status,
            adapter_acknowledgment_state=(
                RuntimeRelayControlAdapterAcknowledgmentState.ACCEPTED
            ),
            protocol_stage_outcome=(
                RuntimeRelayControlProtocolStageOutcome.RELAY_OPERATION_COMPLETED
                if requested_outcome == RuntimeCommandOutcome.SUCCEEDED
                else RuntimeRelayControlProtocolStageOutcome.RELAY_OPERATION_FAILED
            ),
            execution_outcome=requested_outcome,
            error_category=(
                None
                if requested_outcome == RuntimeCommandOutcome.SUCCEEDED
                else RuntimeRelayControlErrorCategory.EXECUTION_FAILED
            ),
            error_detail=error_detail,
            interpreter_summary=(
                "Gurux relay-control invocation was acknowledged and interpreted "
                "into bounded relay-control terminal semantics."
            ),
        )

    if response.invocation_status == "rejected":
        return GuruxRelayControlInterpretedResult(
            invocation_status=response.invocation_status,
            adapter_acknowledgment_state=(
                RuntimeRelayControlAdapterAcknowledgmentState.REJECTED
            ),
            protocol_stage_outcome=(
                RuntimeRelayControlProtocolStageOutcome.RELAY_OPERATION_FAILED
            ),
            execution_outcome=RuntimeCommandOutcome.FAILED,
            error_category=RuntimeRelayControlErrorCategory.ADAPTER_REJECTED,
            error_detail=error_detail or "Gurux relay-control invocation was rejected.",
            interpreter_summary=(
                "Gurux relay-control invocation was explicitly rejected and "
                "interpreted as a bounded terminal relay-control failure."
            ),
        )

    if response.invocation_status == "unavailable":
        return GuruxRelayControlInterpretedResult(
            invocation_status=response.invocation_status,
            adapter_acknowledgment_state=(
                RuntimeRelayControlAdapterAcknowledgmentState.REJECTED
            ),
            protocol_stage_outcome=(
                RuntimeRelayControlProtocolStageOutcome.RELAY_OPERATION_FAILED
            ),
            execution_outcome=RuntimeCommandOutcome.FAILED,
            error_category=RuntimeRelayControlErrorCategory.EXECUTION_FAILED,
            error_detail=error_detail or "Gurux relay-control invocation path is unavailable.",
            interpreter_summary=(
                "Gurux relay-control invocation path was unavailable and interpreted "
                "as a bounded terminal relay-control failure."
            ),
        )

    raise ValueError(
        "Unusable Gurux relay-control invocation stub response for interpreter."
    )


def _build_gurux_relay_control_execution_audit_summary(
    *,
    request: RuntimeRelayControlAdapterRequest | None,
    gurux_operation: GuruxRelayControlOperationDefinition | None,
    resolved_transport_profile: GuruxRelayControlResolvedTransportProfile | None,
    validated_target: GuruxRelayControlValidatedTarget | None,
    normalized_request: GuruxRelayControlNormalizedRequest | None,
    invocation_response: GuruxRelayControlInvocationStubResponse | None,
    interpreted_result: GuruxRelayControlInterpretedResult | None,
) -> GuruxRelayControlExecutionAuditSummary:
    stopped_at_stage = None
    if gurux_operation is None:
        stopped_at_stage = "mapping"
    elif resolved_transport_profile is None:
        stopped_at_stage = "resolution"
    elif validated_target is None:
        stopped_at_stage = "validation"
    elif normalized_request is None:
        stopped_at_stage = "normalization"
    elif invocation_response is None:
        stopped_at_stage = "invocation"
    elif interpreted_result is None:
        stopped_at_stage = "interpretation"

    return GuruxRelayControlExecutionAuditSummary(
        gurux_feature_flag_enabled=settings.enable_runtime_relay_control_gurux_mapper,
        gurux_path_selected=gurux_operation is not None,
        relay_operation=(
            gurux_operation.operation.value
            if gurux_operation is not None
            else None
        ),
        gurux_method_name=gurux_operation.method_name if gurux_operation is not None else None,
        resolved_transport_profile_present=resolved_transport_profile is not None,
        validated_target_present=validated_target is not None,
        normalized_request_present=normalized_request is not None,
        invocation_attempted=invocation_response is not None,
        interpreted_result_present=interpreted_result is not None,
        resolved_transport_locator=(
            str(resolved_transport_profile.transport_profile.get("transport_locator"))
            if resolved_transport_profile is not None
            and resolved_transport_profile.transport_profile.get("transport_locator") is not None
            else None
        ),
        resolved_protocol_profile_id=(
            str(resolved_transport_profile.protocol_profile.get("protocol_profile_id"))
            if resolved_transport_profile is not None
            and resolved_transport_profile.protocol_profile.get("protocol_profile_id") is not None
            else None
        ),
        transport_prerequisites_present=(
            validated_target.transport_prerequisites_present
            if validated_target is not None
            else None
        ),
        security_prerequisites_present=(
            validated_target.security_prerequisites_present
            if validated_target is not None
            else None
        ),
        terminal_invocation_status=(
            invocation_response.invocation_status
            if invocation_response is not None
            else None
        ),
        terminal_execution_outcome=(
            interpreted_result.execution_outcome
            if interpreted_result is not None
            else None
        ),
        correlation_id=(
            request.execution_context.correlation_id if request is not None else None
        ),
        request_id=request.execution_context.request_id if request is not None else None,
        session_identifier=(
            str(request.trace_references.get("session_identifier"))
            if request is not None and request.trace_references.get("session_identifier") is not None
            else None
        ),
        stopped_at_stage=stopped_at_stage,
    )


def _project_gurux_relay_control_execution_phase_state(
    *,
    request: RuntimeRelayControlAdapterRequest | None,
    gurux_operation: GuruxRelayControlOperationDefinition | None,
    resolved_transport_profile: GuruxRelayControlResolvedTransportProfile | None,
    validated_target: GuruxRelayControlValidatedTarget | None,
    normalized_request: GuruxRelayControlNormalizedRequest | None,
    invocation_response: GuruxRelayControlInvocationStubResponse | None,
    interpreted_result: GuruxRelayControlInterpretedResult | None,
    execution_audit_summary: GuruxRelayControlExecutionAuditSummary,
) -> GuruxRelayControlExecutionPhaseProgression:
    return GuruxRelayControlExecutionPhaseProgression(
        gurux_feature_flag_enabled=execution_audit_summary.gurux_feature_flag_enabled,
        gurux_path_selected=execution_audit_summary.gurux_path_selected,
        relay_operation=(
            gurux_operation.operation.value
            if gurux_operation is not None
            else execution_audit_summary.relay_operation
        ),
        resolver_stage_state=(
            "resolved"
            if resolved_transport_profile is not None
            else (
                "not_started"
                if gurux_operation is None
                else "failed"
            )
        ),
        validator_stage_state=(
            "validated"
            if validated_target is not None
            else (
                "not_started"
                if resolved_transport_profile is None
                else "failed"
            )
        ),
        normalizer_stage_state=(
            "normalized"
            if normalized_request is not None
            else (
                "not_started"
                if validated_target is None
                else "failed"
            )
        ),
        invocation_stage_state=(
            invocation_response.invocation_status
            if invocation_response is not None
            else (
                "not_started"
                if normalized_request is None
                else "failed"
            )
        ),
        interpreter_stage_state=(
            interpreted_result.adapter_acknowledgment_state.value
            if interpreted_result is not None
            else (
                "not_started"
                if invocation_response is None
                else "failed"
            )
        ),
        stopped_at_stage=execution_audit_summary.stopped_at_stage,
        terminal_invocation_status=execution_audit_summary.terminal_invocation_status,
        terminal_execution_outcome=execution_audit_summary.terminal_execution_outcome,
        correlation_id=(
            request.execution_context.correlation_id if request is not None else None
        ),
        request_id=request.execution_context.request_id if request is not None else None,
        session_identifier=execution_audit_summary.session_identifier,
    )


def _project_gurux_relay_control_terminal_adapter_status(
    *,
    request: RuntimeRelayControlAdapterRequest | None,
    execution_phase_progression: GuruxRelayControlExecutionPhaseProgression,
    execution_audit_summary: GuruxRelayControlExecutionAuditSummary,
    interpreted_result: GuruxRelayControlInterpretedResult | None,
) -> GuruxRelayControlTerminalAdapterStatus:
    if execution_phase_progression.stopped_at_stage in {"resolution", "validation", "normalization"}:
        adapter_terminal_state = "blocked_pre_invocation"
    elif execution_phase_progression.stopped_at_stage == "invocation":
        adapter_terminal_state = "unavailable"
    elif execution_phase_progression.stopped_at_stage == "interpretation":
        adapter_terminal_state = "unusable_response"
    elif interpreted_result is not None:
        if (
            interpreted_result.adapter_acknowledgment_state
            == RuntimeRelayControlAdapterAcknowledgmentState.ACCEPTED
        ):
            adapter_terminal_state = "acknowledged"
        elif execution_audit_summary.terminal_invocation_status == "unavailable":
            adapter_terminal_state = "unavailable"
        else:
            adapter_terminal_state = "rejected"
    else:
        adapter_terminal_state = "blocked_mid_pipeline"

    terminal_acknowledgment_class = (
        interpreted_result.adapter_acknowledgment_state.value
        if interpreted_result is not None
        else None
    )

    return GuruxRelayControlTerminalAdapterStatus(
        gurux_feature_flag_enabled=execution_phase_progression.gurux_feature_flag_enabled,
        gurux_path_selected=execution_phase_progression.gurux_path_selected,
        relay_operation=execution_phase_progression.relay_operation,
        adapter_terminal_state=adapter_terminal_state,
        terminal_acknowledgment_class=terminal_acknowledgment_class,
        final_execution_disposition=execution_phase_progression.terminal_execution_outcome,
        terminal_invocation_status=execution_phase_progression.terminal_invocation_status,
        stopped_at_stage=execution_phase_progression.stopped_at_stage,
        correlation_id=(
            request.execution_context.correlation_id if request is not None else None
        ),
        request_id=request.execution_context.request_id if request is not None else None,
        session_identifier=execution_audit_summary.session_identifier,
    )


def _map_outcome_to_session_status(outcome: RuntimeCommandOutcome) -> ConnectivitySessionStatus:
    if outcome == RuntimeCommandOutcome.SUCCEEDED:
        return ConnectivitySessionStatus.SUCCEEDED
    if outcome == RuntimeCommandOutcome.TIMED_OUT:
        return ConnectivitySessionStatus.TIMED_OUT
    if outcome == RuntimeCommandOutcome.CANCELLED:
        return ConnectivitySessionStatus.CANCELLED
    return ConnectivitySessionStatus.FAILED
