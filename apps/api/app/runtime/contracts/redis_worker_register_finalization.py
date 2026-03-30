from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRegisterFinalizationSummary(StringEnum):
    REGISTER_FINALIZATION_SUMMARY = "register_finalization_summary"
    FINALIZATION_ACTION_RECORD = "finalization_action_record"
    REGISTER_FINALIZATION_NOTE = "register_finalization_note"
    FINAL_REGISTER_WORKFLOW_ARTIFACT = "final_register_workflow_artifact"
    NOOP_REGISTER_FINALIZATION = "noop_register_finalization"


class RedisWorkerRegisterFinalizationRecord(BaseModel):
    finalization_type: RedisWorkerRegisterFinalizationSummary
    detail: str
    terminal: bool


class RedisWorkerFinalizationArtifact(BaseModel):
    records: list[RedisWorkerRegisterFinalizationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    finalization_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
