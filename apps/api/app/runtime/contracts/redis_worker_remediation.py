from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRemediationSummary(StringEnum):
    REMEDIATION_SUMMARY = "remediation_summary"
    RESPONSE_ACTION_RECORD = "response_action_record"
    REMEDIATION_NOTE = "remediation_note"
    EXCEPTION_RESPONSE_ARTIFACT = "exception_response_artifact"
    NOOP_REMEDIATION = "noop_remediation"


class RedisWorkerRemediationRecord(BaseModel):
    remediation_type: RedisWorkerRemediationSummary
    detail: str
    terminal: bool


class RedisWorkerResponseArtifact(BaseModel):
    records: list[RedisWorkerRemediationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    response_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
