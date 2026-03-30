from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerFinalization(StringEnum):
    RETENTION_READY_RECEIPT = "retention_ready_receipt"
    RETRY_HANDOFF_ENVELOPE = "retry_handoff_envelope"
    DEAD_LETTER_HANDOFF_RECORD = "dead_letter_handoff_record"
    CANCELLATION_FINALIZED_MARKER = "cancellation_finalized_marker"
    NOOP_FINALIZATION = "noop_finalization"


class RedisWorkerFinalizationRecord(BaseModel):
    finalization: RedisWorkerFinalization
    detail: str
    terminal: bool


class RedisWorkerFinalizationTimeline(BaseModel):
    records: list[RedisWorkerFinalizationRecord] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
