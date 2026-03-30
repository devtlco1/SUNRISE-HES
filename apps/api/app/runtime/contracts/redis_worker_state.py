from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerState(StringEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    ACK_PENDING = "ack_pending"
    ACKED = "acked"
    EXPIRED = "expired"
    REDELIVERED = "redelivered"
    FAILED_PLACEHOLDER = "failed_placeholder"


class RedisWorkerStateSnapshot(BaseModel):
    state: RedisWorkerState
    detail: str
    worker_consumer_name: str
    pending_message_id: str
    message_id: str


class RedisWorkerStateTransition(BaseModel):
    from_state: RedisWorkerState
    to_state: RedisWorkerState
    reason: str


class RedisWorkerStateTimeline(BaseModel):
    snapshots: list[RedisWorkerStateSnapshot] = Field(default_factory=list)
    transitions: list[RedisWorkerStateTransition] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
