from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.modules.commands.enums import CommandCategory
from app.modules.connectivity.enums import ProtocolFamily
from app.runtime.contracts.execution import (
    MeterRuntimeTarget,
    RuntimeExecutionContext,
    RuntimeIntentType,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from app.runtime.contracts.results import RuntimeCommandOutcome
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeRelayControlOperation(StringEnum):
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"


class RuntimeRelayControlExecutionStatus(StringEnum):
    COMPLETED = "completed"


class RuntimeRelayControlAdapterAcknowledgmentState(StringEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RuntimeRelayControlProtocolStageOutcome(StringEnum):
    RELAY_OPERATION_COMPLETED = "relay_operation_completed"
    RELAY_OPERATION_FAILED = "relay_operation_failed"


class RuntimeRelayControlErrorCategory(StringEnum):
    ADAPTER_REJECTED = "adapter_rejected"
    EXECUTION_FAILED = "execution_failed"


class RuntimeRelayControlAdapterRequest(BaseModel):
    adapter_key: str
    protocol_family: ProtocolFamily
    operation: RuntimeRelayControlOperation
    command_category: CommandCategory
    execution_context: RuntimeExecutionContext
    target: MeterRuntimeTarget
    transport: RuntimeTransportConfig
    security: RuntimeSecurityMaterialRefs
    protocol_profile_code: str | None = None
    iec62056_21_enabled: bool = False
    iec_device_address: str | None = None
    iec_baud_rate: int | None = None
    client_address: int | None = None
    server_address: int | None = None
    server_address_size: int = 1
    protocol_settings: dict[str, object] | None = None
    protocol_defaults: dict[str, object] | None = None
    request_payload: dict[str, object] | None = None
    normalized_payload: dict[str, object] | None = None
    dispatch_envelope_record_id: str
    trace_references: dict[str, object] = Field(default_factory=dict)
    lineage: RuntimeExecutionSessionLineage


class RuntimeRelayControlExecutionResult(BaseModel):
    status: RuntimeRelayControlExecutionStatus
    relay_control_execution_record_id: str
    session_identifier: str
    dispatch_envelope_record_id: str
    delivery_contract_record_id: str
    envelope_record_id: str
    publication_contract_record_id: str
    attestation_record_id: str
    settlement_record_id: str
    reconciliation_record_id: str
    interpretation_record_id: str
    observation_record_id: str
    invocation_result_record_id: str
    dispatch_request_record_id: str
    selection_record_id: str
    intent_record_id: str
    closure_record_id: str
    materialization_record_id: str
    post_processing_record_id: str
    disposition_record_id: str
    outcome_record_id: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    adapter_key: str
    protocol_family: ProtocolFamily
    relay_operation: RuntimeRelayControlOperation
    command_category: CommandCategory
    adapter_acknowledgment_state: RuntimeRelayControlAdapterAcknowledgmentState
    protocol_stage_outcome: RuntimeRelayControlProtocolStageOutcome
    execution_outcome: RuntimeCommandOutcome
    correlation_id: str | None = None
    request_id: str | None = None
    execution_started_at: str
    execution_finished_at: str
    adapter_result_summary: dict[str, object] = Field(default_factory=dict)
    adapter_response_snapshot: dict[str, object] = Field(default_factory=dict)
    error_category: RuntimeRelayControlErrorCategory | None = None
    error_detail: str | None = None
    relay_control_recorded_by_executor_identifier: str
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
