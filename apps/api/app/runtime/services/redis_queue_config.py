from __future__ import annotations

from app.runtime.contracts import RedisTransportConfigResult
from app.runtime.redis_transport import get_redis_transport_config


def get_effective_redis_transport_config() -> RedisTransportConfigResult:
    return get_redis_transport_config()
