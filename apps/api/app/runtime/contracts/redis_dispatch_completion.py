from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum


class RedisDispatchAckStatus(StringEnum):
    ACKED = "acked"


class RedisDispatchReleaseStatus(StringEnum):
    RELEASED = "released"


class RedisDispatchReleaseMode(StringEnum):
    REQUEUED_COPY = "requeued_copy"


class RedisDispatchAckResult(BaseModel):
    status: RedisDispatchAckStatus
    backend_name: str = "redis"
    stream_name: str
    consumer_group: str
    consumer_name: str
    message_id: str
    claim_token: str
    ack_receipt_id: str
    acked_at: str


class RedisDispatchReleaseResult(BaseModel):
    status: RedisDispatchReleaseStatus
    release_mode: RedisDispatchReleaseMode
    backend_name: str = "redis"
    stream_name: str
    consumer_group: str
    consumer_name: str
    original_message_id: str
    requeued_message_id: str
    claim_token: str
    release_receipt_id: str
    released_at: str
