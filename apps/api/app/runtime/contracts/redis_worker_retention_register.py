from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRetentionRegisterSummary(StringEnum):
    RETENTION_REGISTER_SUMMARY = "retention_register_summary"
    REGISTER_ACTION_RECORD = "register_action_record"
    RETENTION_REGISTER_NOTE = "retention_register_note"
    FINAL_REGISTER_ARTIFACT = "final_register_artifact"
    NOOP_RETENTION_REGISTER = "noop_retention_register"


class RedisWorkerRetentionRegisterRecord(BaseModel):
    register_type: RedisWorkerRetentionRegisterSummary
    detail: str
    terminal: bool


class RedisWorkerRegisterArtifact(BaseModel):
    records: list[RedisWorkerRetentionRegisterRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    register_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
