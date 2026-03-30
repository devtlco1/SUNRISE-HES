from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProtocolInterpretationStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeProtocolInterpretationFamily(StringEnum):
    PLACEHOLDER_PROTOCOL_TERMINAL_INTERPRETATION = (
        "placeholder_protocol_terminal_interpretation"
    )


class RuntimeProtocolInterpretationState(StringEnum):
    PLACEHOLDER_RUNTIME_INTERPRETATION_RECORDED = (
        "placeholder_runtime_interpretation_recorded"
    )


class RuntimeProtocolSemanticOutcomeClassification(StringEnum):
    PLACEHOLDER_TERMINAL_MEANING_READY = "placeholder_terminal_meaning_ready"


class RuntimeProtocolInterpretationPayload(BaseModel):
    schema_version: str
    interpretation_state: RuntimeProtocolInterpretationState
    runtime_meaning_mode: str
    adapter_family: str
    capability_profile: str
    semantic_outcome_classification: RuntimeProtocolSemanticOutcomeClassification
    placeholder_chain_references: dict[str, str]


class RuntimeProtocolInterpretationResult(BaseModel):
    status: RuntimeProtocolInterpretationStatus
    interpretation_record_id: str
    session_identifier: str
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
    terminal_outcome: str
    downstream_state: str
    interpretation_key: str
    interpretation_family: RuntimeProtocolInterpretationFamily
    interpretation_payload: RuntimeProtocolInterpretationPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    interpretation_recorded_at: str
    interpretation_recorded_by_executor_identifier: str
    interpretation_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
