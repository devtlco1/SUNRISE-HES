from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerResponseAssuranceSummary(StringEnum):
    RESPONSE_ASSURANCE_SUMMARY = "response_assurance_summary"
    ASSURANCE_ACTION_RECORD = "assurance_action_record"
    ASSURANCE_NOTE = "assurance_note"
    POST_VERIFICATION_ARTIFACT = "post_verification_artifact"
    NOOP_RESPONSE_ASSURANCE = "noop_response_assurance"


class RedisWorkerResponseAssuranceRecord(BaseModel):
    assurance_type: RedisWorkerResponseAssuranceSummary
    detail: str
    terminal: bool


class RedisWorkerAssuranceArtifact(BaseModel):
    records: list[RedisWorkerResponseAssuranceRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    assurance_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
