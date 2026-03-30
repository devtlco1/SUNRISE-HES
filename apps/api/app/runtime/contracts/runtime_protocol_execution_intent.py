from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProtocolExecutionIntentStatus(StringEnum):
    DERIVED = "derived"


class RuntimeProtocolExecutionIntentType(StringEnum):
    PLACEHOLDER_PROTOCOL_ADAPTER_READY = "placeholder_protocol_adapter_ready"


class RuntimeProtocolExecutionTargetMode(StringEnum):
    DEFERRED_PROTOCOL_EXECUTION_BOUNDARY = "deferred_protocol_execution_boundary"


class RuntimeProtocolExecutionIntentResult(BaseModel):
    status: RuntimeProtocolExecutionIntentStatus
    intent_record_id: str
    session_identifier: str
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
    protocol_execution_intent_type: RuntimeProtocolExecutionIntentType
    target_execution_mode: RuntimeProtocolExecutionTargetMode
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    intent_recorded_at: str
    intent_recorded_by_executor_identifier: str
    intent_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
