from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerOversightSummary(StringEnum):
    OVERSIGHT_SUMMARY = "oversight_summary"
    INTERVENTION_CANDIDATE_RECORD = "intervention_candidate_record"
    OPERATIONS_WATCH_NOTE = "operations_watch_note"
    ESCALATION_REVIEW_ARTIFACT = "escalation_review_artifact"
    NOOP_OVERSIGHT = "noop_oversight"


class RedisWorkerOversightRecord(BaseModel):
    oversight_type: RedisWorkerOversightSummary
    detail: str
    terminal: bool


class RedisWorkerInterventionArtifact(BaseModel):
    records: list[RedisWorkerOversightRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    intervention_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
