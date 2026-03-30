from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRegisterReconciliationSummary(StringEnum):
    REGISTER_RECONCILIATION_SUMMARY = "register_reconciliation_summary"
    RECONCILIATION_ACTION_RECORD = "reconciliation_action_record"
    REGISTER_CLOSE_NOTE = "register_close_note"
    FINAL_REGISTER_CLOSE_ARTIFACT = "final_register_close_artifact"
    NOOP_REGISTER_RECONCILIATION = "noop_register_reconciliation"


class RedisWorkerRegisterReconciliationRecord(BaseModel):
    reconciliation_type: RedisWorkerRegisterReconciliationSummary
    detail: str
    terminal: bool


class RedisWorkerRegisterCloseArtifact(BaseModel):
    records: list[RedisWorkerRegisterReconciliationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    reconciliation_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
