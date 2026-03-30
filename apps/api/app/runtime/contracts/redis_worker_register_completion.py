from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRegisterCompletionSummary(StringEnum):
    REGISTER_COMPLETION_SUMMARY = "register_completion_summary"
    COMPLETION_ACTION_RECORD = "completion_action_record"
    REGISTER_COMPLETION_NOTE = "register_completion_note"
    POST_PUBLICATION_COMPLETION_ARTIFACT = "post_publication_completion_artifact"
    NOOP_REGISTER_COMPLETION = "noop_register_completion"


class RedisWorkerRegisterCompletionRecord(BaseModel):
    completion_type: RedisWorkerRegisterCompletionSummary
    detail: str
    terminal: bool


class RedisWorkerCompletionArtifact(BaseModel):
    records: list[RedisWorkerRegisterCompletionRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    completion_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
