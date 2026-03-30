from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProtocolDispatchRequestStatus(StringEnum):
    ASSEMBLED = "assembled"


class RuntimeProtocolDispatchRequestFamily(StringEnum):
    PLACEHOLDER_PROTOCOL_EXECUTION_REQUEST = "placeholder_protocol_execution_request"


class RuntimeProtocolDispatchActionType(StringEnum):
    PLACEHOLDER_PROTOCOL_INVOCATION_SHAPE_READY = "placeholder_protocol_invocation_shape_ready"


class RuntimeProtocolDispatchEnvelope(BaseModel):
    schema_version: str
    action_type: RuntimeProtocolDispatchActionType
    target_mode: str
    adapter_family: str
    capability_profile: str
    placeholder_chain_references: dict[str, str]


class RuntimeProtocolDispatchRequestResult(BaseModel):
    status: RuntimeProtocolDispatchRequestStatus
    dispatch_request_record_id: str
    session_identifier: str
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
    dispatch_request_key: str
    request_family: RuntimeProtocolDispatchRequestFamily
    execution_envelope: RuntimeProtocolDispatchEnvelope
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    request_recorded_at: str
    request_recorded_by_executor_identifier: str
    request_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
