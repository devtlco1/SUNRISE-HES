from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRegisterPublicationSummary(StringEnum):
    REGISTER_PUBLICATION_SUMMARY = "register_publication_summary"
    PUBLICATION_ACTION_RECORD = "publication_action_record"
    PUBLICATION_NOTE = "publication_note"
    WORKFLOW_COMPLETION_ARTIFACT = "workflow_completion_artifact"
    NOOP_REGISTER_PUBLICATION = "noop_register_publication"


class RedisWorkerRegisterPublicationRecord(BaseModel):
    publication_type: RedisWorkerRegisterPublicationSummary
    detail: str
    terminal: bool


class RedisWorkerPublicationArtifact(BaseModel):
    records: list[RedisWorkerRegisterPublicationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    publication_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
