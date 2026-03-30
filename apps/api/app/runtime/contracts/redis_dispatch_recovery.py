from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.redis_dispatch_claim import RedisDispatchClaimedMessage
from app.runtime.contracts.redis_lifecycle import RedisClaimContract


class RedisDispatchRecoveryStatus(StringEnum):
    RECLAIMED = "reclaimed"


class RedisDispatchPendingEntry(BaseModel):
    message_id: str
    consumer_name: str
    idle_ms: int
    delivery_count: int
    stale: bool
    dispatch_request_identity: str = ""
    dispatch_category: str = ""
    intended_worker_path: str = ""


class RedisDispatchPendingInspectionResult(BaseModel):
    backend_name: str = "redis"
    stream_name: str
    consumer_group: str
    stale_threshold_ms: int
    total_entries: int
    items: list[RedisDispatchPendingEntry] = Field(default_factory=list)


class RedisDispatchRecoveryResult(BaseModel):
    status: RedisDispatchRecoveryStatus
    backend_name: str = "redis"
    stream_name: str
    consumer_group: str
    consumer_name: str
    original_consumer_name: str
    message_id: str
    stale_threshold_ms: int
    idle_ms: int
    delivery_count: int
    claim: RedisClaimContract
    recovery_receipt_id: str
    recovered_at: str
    message: RedisDispatchClaimedMessage
