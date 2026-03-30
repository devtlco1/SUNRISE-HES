from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerCompletionAttestationSummary(StringEnum):
    COMPLETION_ATTESTATION_SUMMARY = "completion_attestation_summary"
    ATTESTATION_ACTION_RECORD = "attestation_action_record"
    ATTESTATION_NOTE = "attestation_note"
    COMPLETION_PROOF_ARTIFACT = "completion_proof_artifact"
    NOOP_COMPLETION_ATTESTATION = "noop_completion_attestation"


class RedisWorkerCompletionAttestationRecord(BaseModel):
    attestation_type: RedisWorkerCompletionAttestationSummary
    detail: str
    terminal: bool


class RedisWorkerCompletionProofArtifact(BaseModel):
    records: list[RedisWorkerCompletionAttestationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    attestation_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
