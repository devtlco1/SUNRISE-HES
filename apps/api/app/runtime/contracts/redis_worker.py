from __future__ import annotations

from pydantic import BaseModel, Field


class RedisWorkerConsumeContract(BaseModel):
    dequeue_result: str
    worker_consumer_name: str
    pending_message_id: str
    simulated_pending_state: str


class RedisWorkerClaimResult(BaseModel):
    claim_result: str
    claim_token: str
    lease_expiration_seconds: int
    simulated_pending_state: str


class RedisWorkerAckResult(BaseModel):
    ack_result: str
    ack_token: str
    simulated_ack_state: str


class RedisWorkerRedeliveryResult(BaseModel):
    redelivery_result: str
    redelivery_decision: str
    redelivery_count: int


class RedisWorkerConsumptionResult(BaseModel):
    consume: RedisWorkerConsumeContract
    claim: RedisWorkerClaimResult
    ack: RedisWorkerAckResult
    redelivery: RedisWorkerRedeliveryResult
    metadata: dict[str, object] = Field(default_factory=dict)
