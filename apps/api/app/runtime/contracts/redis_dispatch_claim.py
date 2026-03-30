from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.redis_lifecycle import RedisClaimContract, RedisDequeueContract


class RedisDispatchClaimStatus(StringEnum):
    CLAIMED = "claimed"
    EMPTY = "empty"


class RedisDispatchClaimedMessage(BaseModel):
    message_id: str
    dispatch_request_identity: str
    dispatch_category: str
    payload_version: str
    intended_worker_path: str
    source_identifiers: dict[str, str | None] = Field(default_factory=dict)
    correlation_lineage: dict[str, str | None] = Field(default_factory=dict)
    dispatch_metadata: dict[str, object] = Field(default_factory=dict)
    body: dict[str, object] = Field(default_factory=dict)
    delivery_count: int = 1
    claimed_at: str


class RedisDispatchClaimResult(BaseModel):
    status: RedisDispatchClaimStatus
    backend_name: str = "redis"
    stream_name: str
    consumer_group: str
    consumer_name: str
    dequeue: RedisDequeueContract | None = None
    claim: RedisClaimContract | None = None
    message: RedisDispatchClaimedMessage | None = None
