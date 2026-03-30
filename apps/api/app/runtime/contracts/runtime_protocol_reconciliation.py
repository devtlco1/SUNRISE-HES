from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeProtocolReconciliationStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeProtocolReconciliationFamily(StringEnum):
    PLACEHOLDER_PROTOCOL_RUNTIME_RECONCILIATION = (
        "placeholder_protocol_runtime_reconciliation"
    )


class RuntimeProtocolReconciliationState(StringEnum):
    PLACEHOLDER_RUNTIME_RECONCILIATION_RECORDED = (
        "placeholder_runtime_reconciliation_recorded"
    )


class RuntimeProtocolRuntimeSemanticReconciliationClassification(StringEnum):
    PLACEHOLDER_PROTOCOL_MEANING_RECONCILED = "placeholder_protocol_meaning_reconciled"


class RuntimeProtocolReconciliationPayload(BaseModel):
    schema_version: str
    reconciliation_state: RuntimeProtocolReconciliationState
    runtime_reconciliation_mode: str
    adapter_family: str
    capability_profile: str
    runtime_semantic_reconciliation_classification: (
        RuntimeProtocolRuntimeSemanticReconciliationClassification
    )
    placeholder_chain_references: dict[str, str]


class RuntimeProtocolReconciliationResult(BaseModel):
    status: RuntimeProtocolReconciliationStatus
    reconciliation_record_id: str
    session_identifier: str
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
    reconciliation_key: str
    reconciliation_family: RuntimeProtocolReconciliationFamily
    reconciliation_payload: RuntimeProtocolReconciliationPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    reconciliation_recorded_at: str
    reconciliation_recorded_by_executor_identifier: str
    reconciliation_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
