from __future__ import annotations

from pydantic import BaseModel, Field


class RedisQueueReceiptContract(BaseModel):
    message_id: str
    receipt_id: str
    ack_required: bool = True


class RedisQueueDeliveryContract(BaseModel):
    stream_name: str
    consumer_group: str
    routing_key: str
    claim_timeout_seconds: int = 300
    delivery_attempt: int = 0
    dead_letter_stream: str | None = None


class RedisQueueSemantics(BaseModel):
    backend_name: str = "redis_placeholder"
    delivery: RedisQueueDeliveryContract
    receipt: RedisQueueReceiptContract
    metadata: dict[str, object] = Field(default_factory=dict)
