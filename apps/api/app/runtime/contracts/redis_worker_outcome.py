from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerOutcome(StringEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"
    TIMEOUT = "timeout"
    CANCELLED_PLACEHOLDER = "cancelled_placeholder"


class RedisWorkerOutcomeRecord(BaseModel):
    outcome: RedisWorkerOutcome
    detail: str
    terminal: bool


class RedisWorkerOutcomeTimeline(BaseModel):
    records: list[RedisWorkerOutcomeRecord] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
