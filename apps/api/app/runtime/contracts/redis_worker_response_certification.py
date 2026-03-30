from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerResponseCertificationSummary(StringEnum):
    RESPONSE_CERTIFICATION_SUMMARY = "response_certification_summary"
    CERTIFICATION_ACTION_RECORD = "certification_action_record"
    CERTIFICATION_NOTE = "certification_note"
    COMPLETION_CERTIFICATION_ARTIFACT = "completion_certification_artifact"
    NOOP_RESPONSE_CERTIFICATION = "noop_response_certification"


class RedisWorkerResponseCertificationRecord(BaseModel):
    certification_type: RedisWorkerResponseCertificationSummary
    detail: str
    terminal: bool


class RedisWorkerCertificationArtifact(BaseModel):
    records: list[RedisWorkerResponseCertificationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    certification_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
