from __future__ import annotations

from datetime import UTC, datetime

from app.modules.connectivity.enums import ConnectivitySessionStatus, ProtocolFamily
from app.modules.events.enums import EventSeverity, EventState
from app.modules.readings.enums import ReadingBatchStatus, ReadingSourceType, ReadingType
from app.runtime.adapters.base import BaseRuntimeAdapter
from app.runtime.contracts import (
    ProtocolExecutionPlan,
    RuntimeCommandOutcome,
    RuntimeCommandResult,
    RuntimeEventPayload,
    RuntimeReadingBatchPayload,
    RuntimeReadingPayload,
    RuntimeSessionResult,
)


class DlmsCosemRuntimeAdapter(BaseRuntimeAdapter):
    adapter_key = "dlms-cosem-runtime"
    supported_protocol_families = (ProtocolFamily.DLMS_COSEM,)

    def execute(self, plan: ProtocolExecutionPlan) -> RuntimeCommandResult:
        raise NotImplementedError(
            "DLMS/COSEM runtime execution is intentionally not implemented yet. "
            "This adapter only defines the worker-facing contract boundary."
        )


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
        if mock_execution.get("include_placeholder_readings"):
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
            )

        events: list[RuntimeEventPayload] = []
        if mock_execution.get("include_placeholder_events"):
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


def _map_outcome_to_session_status(outcome: RuntimeCommandOutcome) -> ConnectivitySessionStatus:
    if outcome == RuntimeCommandOutcome.SUCCEEDED:
        return ConnectivitySessionStatus.SUCCEEDED
    if outcome == RuntimeCommandOutcome.TIMED_OUT:
        return ConnectivitySessionStatus.TIMED_OUT
    if outcome == RuntimeCommandOutcome.CANCELLED:
        return ConnectivitySessionStatus.CANCELLED
    return ConnectivitySessionStatus.FAILED
