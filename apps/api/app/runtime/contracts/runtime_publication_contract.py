from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimePublicationContractStatus(StringEnum):
    RECORDED = "recorded"


class RuntimePublicationContractFamily(StringEnum):
    PLACEHOLDER_RUNTIME_PUBLICATION_CONTRACT = (
        "placeholder_runtime_publication_contract"
    )


class RuntimePublicationContractState(StringEnum):
    PLACEHOLDER_RUNTIME_PUBLICATION_CONTRACT_READY = (
        "placeholder_runtime_publication_contract_ready"
    )


class RuntimePublicationContractClassification(StringEnum):
    PLACEHOLDER_EXTERNALLY_PUBLISHABLE_RUNTIME_FINALIZATION_READY = (
        "placeholder_externally_publishable_runtime_finalization_ready"
    )


class RuntimePublicationConsumerScope(StringEnum):
    PLACEHOLDER_RUNTIME_CONSUMER = "placeholder_runtime_consumer"


class RuntimePublicationContractPayload(BaseModel):
    schema_version: str
    publication_state: RuntimePublicationContractState
    publication_projection_mode: str
    adapter_family: str
    capability_profile: str
    publication_classification: RuntimePublicationContractClassification
    consumer_scope: RuntimePublicationConsumerScope
    placeholder_chain_references: dict[str, str]


class RuntimePublicationContractResult(BaseModel):
    status: RuntimePublicationContractStatus
    publication_contract_record_id: str
    session_identifier: str
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
    terminal_outcome: str
    downstream_state: str
    publication_contract_key: str
    publication_contract_family: RuntimePublicationContractFamily
    publication_contract_payload: RuntimePublicationContractPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    publication_contract_recorded_at: str
    publication_contract_recorded_by_executor_identifier: str
    publication_contract_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
