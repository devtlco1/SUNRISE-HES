from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeDispatchEnvelopeStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeDispatchEnvelopeFamily(StringEnum):
    PLACEHOLDER_RUNTIME_DISPATCH_ENVELOPE = "placeholder_runtime_dispatch_envelope"


class RuntimeDispatchEnvelopeState(StringEnum):
    PLACEHOLDER_HANDOFF_READINESS_RECORDED = "placeholder_handoff_readiness_recorded"


class RuntimeDispatchEnvelopeClassification(StringEnum):
    PLACEHOLDER_RUNTIME_DISPATCH_ENVELOPE_READY = (
        "placeholder_runtime_dispatch_envelope_ready"
    )


class RuntimeDispatchOutboundChannelFamily(StringEnum):
    PLACEHOLDER_OUTBOUND_DELIVERY_CHANNEL = "placeholder_outbound_delivery_channel"


class RuntimeDispatchEnvelopePayload(BaseModel):
    schema_version: str
    dispatch_envelope_state: RuntimeDispatchEnvelopeState
    handoff_readiness_mode: str
    adapter_family: str
    capability_profile: str
    dispatch_classification: RuntimeDispatchEnvelopeClassification
    outbound_channel_family: RuntimeDispatchOutboundChannelFamily
    placeholder_chain_references: dict[str, str]


class RuntimeDispatchEnvelopeResult(BaseModel):
    status: RuntimeDispatchEnvelopeStatus
    dispatch_envelope_record_id: str
    session_identifier: str
    delivery_contract_record_id: str
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
    dispatch_envelope_key: str
    dispatch_envelope_family: RuntimeDispatchEnvelopeFamily
    dispatch_envelope_payload: RuntimeDispatchEnvelopePayload
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    dispatch_envelope_recorded_at: str
    dispatch_envelope_recorded_by_executor_identifier: str
    dispatch_envelope_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
