from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeTerminalSettlementStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeTerminalSettlementFamily(StringEnum):
    PLACEHOLDER_TERMINAL_RUNTIME_SETTLEMENT = (
        "placeholder_terminal_runtime_settlement"
    )


class RuntimeTerminalSettlementState(StringEnum):
    PLACEHOLDER_TERMINAL_RUNTIME_SETTLEMENT_RECORDED = (
        "placeholder_terminal_runtime_settlement_recorded"
    )


class RuntimeTerminalSettlementClassification(StringEnum):
    PLACEHOLDER_FINAL_RUNTIME_PROJECTION_READY = (
        "placeholder_final_runtime_projection_ready"
    )


class RuntimeTerminalSettlementPayload(BaseModel):
    schema_version: str
    settlement_state: RuntimeTerminalSettlementState
    terminal_projection_mode: str
    adapter_family: str
    capability_profile: str
    terminal_runtime_settlement_classification: RuntimeTerminalSettlementClassification
    placeholder_chain_references: dict[str, str]


class RuntimeTerminalSettlementResult(BaseModel):
    status: RuntimeTerminalSettlementStatus
    settlement_record_id: str
    session_identifier: str
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
    terminal_outcome: str
    downstream_state: str
    settlement_key: str
    settlement_family: RuntimeTerminalSettlementFamily
    settlement_payload: RuntimeTerminalSettlementPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    settlement_recorded_at: str
    settlement_recorded_by_executor_identifier: str
    settlement_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
