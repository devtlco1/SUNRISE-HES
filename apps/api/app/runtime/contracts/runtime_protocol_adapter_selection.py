from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProtocolAdapterSelectionStatus(StringEnum):
    RESOLVED = "resolved"


class RuntimeProtocolAdapterFamily(StringEnum):
    PLACEHOLDER_PROTOCOL_BOUNDARY_ADAPTER = "placeholder_protocol_boundary_adapter"


class RuntimeProtocolAdapterCapabilityProfile(StringEnum):
    PLACEHOLDER_PROTOCOL_DISPATCH_SHAPE_READY = "placeholder_protocol_dispatch_shape_ready"


class RuntimeProtocolAdapterCapability(StringEnum):
    SUPPORTS_PLACEHOLDER_RELAY_CONTROL = "supports_placeholder_relay_control"
    SUPPORTS_PLACEHOLDER_READ_PROFILE = "supports_placeholder_read_profile"
    SUPPORTS_PLACEHOLDER_SESSION_DISPATCH = "supports_placeholder_session_dispatch"


class RuntimeProtocolAdapterSelectionResult(BaseModel):
    status: RuntimeProtocolAdapterSelectionStatus
    selection_record_id: str
    session_identifier: str
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
    terminal_outcome: str
    downstream_state: str
    selected_adapter_key: str
    adapter_family: RuntimeProtocolAdapterFamily
    capability_profile: RuntimeProtocolAdapterCapabilityProfile
    supported_placeholder_capabilities: list[RuntimeProtocolAdapterCapability] = Field(
        default_factory=list
    )
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    selection_recorded_at: str
    selection_recorded_by_executor_identifier: str
    selection_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
