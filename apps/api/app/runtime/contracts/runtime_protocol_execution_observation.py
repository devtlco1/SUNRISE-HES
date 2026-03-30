from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProtocolExecutionObservationStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeProtocolExecutionObservationFamily(StringEnum):
    PLACEHOLDER_PROTOCOL_EXECUTION_OBSERVATION = (
        "placeholder_protocol_execution_observation"
    )


class RuntimeProtocolNormalizationState(StringEnum):
    PLACEHOLDER_PROTOCOL_RESPONSE_NORMALIZED = "placeholder_protocol_response_normalized"


class RuntimeProtocolExecutionObservationPayload(BaseModel):
    schema_version: str
    normalization_state: RuntimeProtocolNormalizationState
    observation_mode: str
    adapter_family: str
    capability_profile: str
    placeholder_chain_references: dict[str, str]


class RuntimeProtocolExecutionObservationResult(BaseModel):
    status: RuntimeProtocolExecutionObservationStatus
    observation_record_id: str
    session_identifier: str
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
    observation_key: str
    observation_family: RuntimeProtocolExecutionObservationFamily
    observation_payload: RuntimeProtocolExecutionObservationPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    observation_recorded_at: str
    observation_recorded_by_executor_identifier: str
    observation_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
