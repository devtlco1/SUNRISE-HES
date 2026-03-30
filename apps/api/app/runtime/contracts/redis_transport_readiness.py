from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum


class RedisTransportReadinessStatus(StringEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class RedisTransportReadinessResult(BaseModel):
    backend_name: str = "redis"
    status: RedisTransportReadinessStatus
    ready: bool
    validate_on_startup: bool
    ensure_stream_on_startup: bool
    ensure_consumer_group_on_startup: bool
    validation_performed: bool
    bootstrap_applied: bool = False
    redis_reachable: bool
    stream_name: str
    stream_ready: bool
    consumer_group_name: str
    consumer_group_ready: bool
    checked_at: str
    summary: str
