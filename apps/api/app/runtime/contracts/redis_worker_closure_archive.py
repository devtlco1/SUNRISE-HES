from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerClosureArchiveSummary(StringEnum):
    CLOSURE_ARCHIVE_SUMMARY = "closure_archive_summary"
    ARCHIVE_REGISTER_RECORD = "archive_register_record"
    RETENTION_NOTE = "retention_note"
    FINAL_RETENTION_ARTIFACT = "final_retention_artifact"
    NOOP_CLOSURE_ARCHIVE = "noop_closure_archive"


class RedisWorkerClosureArchiveRecord(BaseModel):
    archive_type: RedisWorkerClosureArchiveSummary
    detail: str
    terminal: bool


class RedisWorkerRetentionArtifact(BaseModel):
    records: list[RedisWorkerClosureArchiveRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    archive_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
