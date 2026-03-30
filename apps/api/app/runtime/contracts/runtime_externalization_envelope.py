from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeExternalizationEnvelopeStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeExternalizationEnvelopeFamily(StringEnum):
    PLACEHOLDER_RUNTIME_EXTERNALIZATION_ENVELOPE = (
        "placeholder_runtime_externalization_envelope"
    )


class RuntimeExternalizationEnvelopeState(StringEnum):
    PLACEHOLDER_EXTERNALIZATION_ENVELOPE_RECORDED = (
        "placeholder_externalization_envelope_recorded"
    )


class RuntimeExternalizationEnvelopeClassification(StringEnum):
    PLACEHOLDER_RUNTIME_DELIVERY_READINESS_READY = (
        "placeholder_runtime_delivery_readiness_ready"
    )


class RuntimeExternalizationTargetChannelFamily(StringEnum):
    PLACEHOLDER_EXTERNAL_RUNTIME_DELIVERY = "placeholder_external_runtime_delivery"


class RuntimeExternalizationEnvelopePayload(BaseModel):
    schema_version: str
    envelope_state: RuntimeExternalizationEnvelopeState
    delivery_projection_mode: str
    adapter_family: str
    capability_profile: str
    delivery_readiness_classification: RuntimeExternalizationEnvelopeClassification
    target_channel_family: RuntimeExternalizationTargetChannelFamily
    placeholder_chain_references: dict[str, str]


class RuntimeExternalizationEnvelopeResult(BaseModel):
    status: RuntimeExternalizationEnvelopeStatus
    envelope_record_id: str
    session_identifier: str
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
    envelope_key: str
    envelope_family: RuntimeExternalizationEnvelopeFamily
    envelope_payload: RuntimeExternalizationEnvelopePayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    envelope_recorded_at: str
    envelope_recorded_by_executor_identifier: str
    envelope_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
