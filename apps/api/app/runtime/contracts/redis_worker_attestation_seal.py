from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerAttestationSealSummary(StringEnum):
    ATTESTATION_SEAL_SUMMARY = "attestation_seal_summary"
    SEAL_ACTION_RECORD = "seal_action_record"
    SEAL_NOTE = "seal_note"
    FINAL_PROOF_ARTIFACT = "final_proof_artifact"
    NOOP_ATTESTATION_SEAL = "noop_attestation_seal"


class RedisWorkerAttestationSealRecord(BaseModel):
    seal_type: RedisWorkerAttestationSealSummary
    detail: str
    terminal: bool


class RedisWorkerSealArtifact(BaseModel):
    records: list[RedisWorkerAttestationSealRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    seal_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
