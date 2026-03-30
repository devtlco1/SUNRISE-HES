from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProtocolInvocationResultStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeProtocolInvocationResultFamily(StringEnum):
    PLACEHOLDER_PROTOCOL_INVOCATION_RESULT = "placeholder_protocol_invocation_result"


class RuntimeProtocolInvocationAcknowledgmentState(StringEnum):
    PLACEHOLDER_PROTOCOL_INVOCATION_ACKNOWLEDGED = (
        "placeholder_protocol_invocation_acknowledged"
    )


class RuntimeProtocolInvocationPayload(BaseModel):
    schema_version: str
    acknowledgment_state: RuntimeProtocolInvocationAcknowledgmentState
    invocation_mode: str
    adapter_family: str
    capability_profile: str
    placeholder_chain_references: dict[str, str]


class RuntimeProtocolInvocationResult(BaseModel):
    status: RuntimeProtocolInvocationResultStatus
    invocation_result_record_id: str
    session_identifier: str
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
    terminal_outcome: str
    downstream_state: str
    invocation_result_key: str
    result_family: RuntimeProtocolInvocationResultFamily
    invocation_payload: RuntimeProtocolInvocationPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    result_recorded_at: str
    result_recorded_by_executor_identifier: str
    result_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
