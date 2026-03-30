from __future__ import annotations

from pydantic import BaseModel


class RedisTransportConfigResult(BaseModel):
    backend_name: str = "redis"
    stream_name: str
    consumer_group_name: str
    claim_timeout_seconds: int
    stale_claim_threshold_seconds: int
    dead_letter_stream_name: str
    validate_on_startup: bool
    ensure_stream_on_startup: bool
    ensure_consumer_group_on_startup: bool
    summary: str
