from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerSettlementAttestationSummary(StringEnum):
    SETTLEMENT_ATTESTATION_SUMMARY = "settlement_attestation_summary"
    ATTESTATION_ACTION_RECORD = "attestation_action_record"
    SETTLEMENT_ATTESTATION_NOTE = "settlement_attestation_note"
    POST_SETTLEMENT_PROOF_ARTIFACT = "post_settlement_proof_artifact"
    NOOP_SETTLEMENT_ATTESTATION = "noop_settlement_attestation"


class RedisWorkerSettlementAttestationRecord(BaseModel):
    attestation_type: RedisWorkerSettlementAttestationSummary
    detail: str
    terminal: bool


class RedisWorkerSettlementProofArtifact(BaseModel):
    records: list[RedisWorkerSettlementAttestationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    attestation_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
