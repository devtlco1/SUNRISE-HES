from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum


class RedisTransportStatusLevel(StringEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class RedisTransportStatusResult(BaseModel):
    backend_name: str = "redis"
    status: RedisTransportStatusLevel
    ready: bool
    stream_name: str
    stream_exists: bool
    stream_depth: int
    consumer_group_name: str
    consumer_group_exists: bool
    consumer_count: int = 0
    pending_count: int = 0
    inspected_pending_count: int = 0
    stale_pending_count: int = 0
    oldest_pending_idle_ms: int | None = None
    stale_threshold_ms: int
    lag: int | None = None
    summary: str
