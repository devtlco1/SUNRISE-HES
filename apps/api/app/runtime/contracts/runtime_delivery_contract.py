from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeDeliveryContractStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeDeliveryContractFamily(StringEnum):
    PLACEHOLDER_RUNTIME_DELIVERY_CONTRACT = "placeholder_runtime_delivery_contract"


class RuntimeDeliveryContractState(StringEnum):
    PLACEHOLDER_DISPATCH_READINESS_RECORDED = "placeholder_dispatch_readiness_recorded"


class RuntimeDeliveryContractClassification(StringEnum):
    PLACEHOLDER_RUNTIME_DELIVERY_CONTRACT_READY = (
        "placeholder_runtime_delivery_contract_ready"
    )


class RuntimeDeliveryTargetFamily(StringEnum):
    PLACEHOLDER_EXTERNAL_DELIVERY_DISPATCH = "placeholder_external_delivery_dispatch"


class RuntimeDeliveryContractPayload(BaseModel):
    schema_version: str
    delivery_state: RuntimeDeliveryContractState
    dispatch_readiness_mode: str
    adapter_family: str
    capability_profile: str
    dispatch_readiness_classification: RuntimeDeliveryContractClassification
    delivery_target_family: RuntimeDeliveryTargetFamily
    placeholder_chain_references: dict[str, str]


class RuntimeDeliveryContractResult(BaseModel):
    status: RuntimeDeliveryContractStatus
    delivery_contract_record_id: str
    session_identifier: str
    envelope_record_id: str
    publication_contract_record_id: str
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
    delivery_contract_key: str
    delivery_contract_family: RuntimeDeliveryContractFamily
    delivery_contract_payload: RuntimeDeliveryContractPayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    delivery_contract_recorded_at: str
    delivery_contract_recorded_by_executor_identifier: str
    delivery_contract_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
