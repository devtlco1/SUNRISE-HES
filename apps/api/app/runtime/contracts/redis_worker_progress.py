from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerProgressStage(StringEnum):
    STARTED = "started"
    CHECKPOINT_REACHED = "checkpoint_reached"
    PARTIALLY_PROCESSED = "partially_processed"
    WAITING_FOR_ACK = "waiting_for_ack"
    COMPLETED_PLACEHOLDER = "completed_placeholder"
    REDELIVERY_PENDING = "redelivery_pending"
    STALLED_PLACEHOLDER = "stalled_placeholder"


class RedisWorkerProgressCheckpoint(BaseModel):
    stage: RedisWorkerProgressStage
    detail: str
    worker_consumer_name: str
    message_id: str


class RedisWorkerProgressOutcome(BaseModel):
    outcome: RedisWorkerProgressStage
    detail: str
    redelivery_decision: str | None = None


class RedisWorkerProgressTimeline(BaseModel):
    checkpoints: list[RedisWorkerProgressCheckpoint] = Field(default_factory=list)
    outcomes: list[RedisWorkerProgressOutcome] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
