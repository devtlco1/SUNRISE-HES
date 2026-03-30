from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerGovernanceSummary(StringEnum):
    GOVERNANCE_SUMMARY = "governance_summary"
    POLICY_REVIEW_RECORD = "policy_review_record"
    COMPLIANCE_CONTROL_SUMMARY = "compliance_control_summary"
    OPERATIONAL_GOVERNANCE_NOTE = "operational_governance_note"
    NOOP_GOVERNANCE = "noop_governance"


class RedisWorkerGovernanceRecord(BaseModel):
    governance_type: RedisWorkerGovernanceSummary
    detail: str
    terminal: bool


class RedisWorkerPolicyReview(BaseModel):
    records: list[RedisWorkerGovernanceRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    review_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
