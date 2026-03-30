from __future__ import annotations

from app.core.config import settings
from app.runtime.contracts import RedisTransportConfigResult


def get_redis_transport_config() -> RedisTransportConfigResult:
    dead_letter_stream_name = (
        settings.redis_queue_dead_letter_stream_name
        or f"{settings.redis_queue_stream_name}:dead-letter"
    )
    return RedisTransportConfigResult(
        stream_name=settings.redis_queue_stream_name,
        consumer_group_name=settings.redis_queue_consumer_group_name,
        claim_timeout_seconds=settings.redis_queue_claim_timeout_seconds,
        stale_claim_threshold_seconds=settings.redis_queue_stale_claim_threshold_seconds,
        dead_letter_stream_name=dead_letter_stream_name,
        validate_on_startup=settings.redis_queue_validate_on_startup,
        ensure_stream_on_startup=settings.redis_queue_ensure_stream_on_startup,
        ensure_consumer_group_on_startup=settings.redis_queue_ensure_consumer_group_on_startup,
        summary=(
            "Redis transport defaults are configured for the dispatch stream, "
            "consumer group, claim lease, stale-claim threshold, and dead-letter naming."
        ),
    )
