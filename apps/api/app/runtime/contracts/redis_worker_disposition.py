from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerDisposition(StringEnum):
    ARCHIVE_READY = "archive_ready"
    RETRY_QUEUE_READY = "retry_queue_ready"
    DEAD_LETTER_READY = "dead_letter_ready"
    CANCELLATION_CLOSED = "cancellation_closed"
    NOOP_DISPOSITION = "noop_disposition"


class RedisWorkerDispositionRecord(BaseModel):
    disposition: RedisWorkerDisposition
    detail: str
    terminal: bool


class RedisWorkerDispositionTimeline(BaseModel):
    records: list[RedisWorkerDispositionRecord] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
