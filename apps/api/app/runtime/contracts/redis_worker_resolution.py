from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerResolution(StringEnum):
    FINAL_ACK = "final_ack"
    DEAD_LETTER_PLACEHOLDER = "dead_letter_placeholder"
    RETRY_SCHEDULED_HINT = "retry_scheduled_hint"
    CANCELLATION_RESOLVED = "cancellation_resolved"
    NOOP_RESOLUTION = "noop_resolution"


class RedisWorkerResolutionRecord(BaseModel):
    resolution: RedisWorkerResolution
    detail: str
    terminal: bool


class RedisWorkerResolutionTimeline(BaseModel):
    records: list[RedisWorkerResolutionRecord] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
