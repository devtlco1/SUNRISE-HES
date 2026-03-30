from __future__ import annotations

from pydantic import BaseModel, Field


class RedisDequeueContract(BaseModel):
    consumer_name: str
    stream_name: str
    consumer_group: str
    pending_message_id: str
    claim_timeout_seconds: int
    delivery_count: int = 0


class RedisClaimContract(BaseModel):
    pending_message_id: str
    claim_token: str
    consumer_name: str
    claim_timeout_seconds: int


class RedisAckContract(BaseModel):
    message_id: str
    receipt_id: str
    ack_token: str
    consumer_group: str


class RedisRedeliveryContract(BaseModel):
    message_id: str
    redelivery_count: int = 0
    stale_claim_hint: bool = False
    retry_claim_hint: bool = True
    dead_letter_stream: str | None = None


class RedisMessageLifecycleContract(BaseModel):
    dequeue: RedisDequeueContract
    claim: RedisClaimContract
    ack: RedisAckContract
    redelivery: RedisRedeliveryContract
    metadata: dict[str, object] = Field(default_factory=dict)
