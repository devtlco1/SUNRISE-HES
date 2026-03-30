from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerAttestationClosureSummary(StringEnum):
    ATTESTATION_CLOSURE_SUMMARY = "attestation_closure_summary"
    CLOSURE_ACTION_RECORD = "closure_action_record"
    ATTESTATION_CLOSURE_NOTE = "attestation_closure_note"
    POST_ATTESTATION_CLOSURE_ARTIFACT = "post_attestation_closure_artifact"
    NOOP_ATTESTATION_CLOSURE = "noop_attestation_closure"


class RedisWorkerAttestationClosureRecord(BaseModel):
    closure_type: RedisWorkerAttestationClosureSummary
    detail: str
    terminal: bool


class RedisWorkerClosureProofArtifact(BaseModel):
    records: list[RedisWorkerAttestationClosureRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    closure_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
