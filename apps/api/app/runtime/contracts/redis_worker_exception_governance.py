from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerExceptionGovernanceSummary(StringEnum):
    EXCEPTION_GOVERNANCE_SUMMARY = "exception_governance_summary"
    INTERVENTION_DECISION_RECORD = "intervention_decision_record"
    EXCEPTION_REVIEW_NOTE = "exception_review_note"
    GOVERNANCE_EXCEPTION_ARTIFACT = "governance_exception_artifact"
    NOOP_EXCEPTION_GOVERNANCE = "noop_exception_governance"


class RedisWorkerExceptionGovernanceRecord(BaseModel):
    governance_type: RedisWorkerExceptionGovernanceSummary
    detail: str
    terminal: bool


class RedisWorkerInterventionDecision(BaseModel):
    records: list[RedisWorkerExceptionGovernanceRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    decision_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
