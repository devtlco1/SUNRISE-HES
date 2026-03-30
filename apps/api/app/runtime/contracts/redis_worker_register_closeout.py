from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRegisterCloseoutSummary(StringEnum):
    REGISTER_CLOSEOUT_SUMMARY = "register_closeout_summary"
    CLOSEOUT_ACTION_RECORD = "closeout_action_record"
    REGISTER_CLOSEOUT_NOTE = "register_closeout_note"
    FINAL_REGISTER_SUMMARY_ARTIFACT = "final_register_summary_artifact"
    NOOP_REGISTER_CLOSEOUT = "noop_register_closeout"


class RedisWorkerRegisterCloseoutRecord(BaseModel):
    closeout_type: RedisWorkerRegisterCloseoutSummary
    detail: str
    terminal: bool


class RedisWorkerCloseoutArtifact(BaseModel):
    records: list[RedisWorkerRegisterCloseoutRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    closeout_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
