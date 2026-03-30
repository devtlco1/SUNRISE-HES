from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeClosureAttestationStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeClosureAttestationFamily(StringEnum):
    PLACEHOLDER_RUNTIME_CLOSURE_ATTESTATION = (
        "placeholder_runtime_closure_attestation"
    )


class RuntimeClosureAttestationState(StringEnum):
    PLACEHOLDER_RUNTIME_CLOSURE_ATTESTED = "placeholder_runtime_closure_attested"


class RuntimeClosureAttestationClassification(StringEnum):
    PLACEHOLDER_EXTERNALLY_CONSUMABLE_FINALIZATION_READY = (
        "placeholder_externally_consumable_finalization_ready"
    )


class RuntimeClosureAttestationPayload(BaseModel):
    schema_version: str
    attestation_state: RuntimeClosureAttestationState
    finalization_projection_mode: str
    adapter_family: str
    capability_profile: str
    closure_attestation_classification: RuntimeClosureAttestationClassification
    placeholder_chain_references: dict[str, str]


class RuntimeClosureAttestationResult(BaseModel):
    status: RuntimeClosureAttestationStatus
    attestation_record_id: str
    session_identifier: str
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
    terminal_outcome: str
    downstream_state: str
    attestation_key: str
    attestation_family: RuntimeClosureAttestationFamily
    attestation_payload: RuntimeClosureAttestationPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    attestation_recorded_at: str
    attestation_recorded_by_executor_identifier: str
    attestation_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
