from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from redis.exceptions import RedisError, ResponseError

from app.runtime.contracts import (
    RedisTransportReadinessResult,
    RedisTransportReadinessStatus,
)
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_transport import get_redis_transport_config
from app.runtime.services.redis_queue_admin import ensure_redis_consumer_group


def evaluate_redis_transport_readiness(
    *,
    apply_startup_policy: bool,
) -> RedisTransportReadinessResult:
    transport_config = get_redis_transport_config()
    checked_at = datetime.now(UTC).isoformat()
    if apply_startup_policy and not transport_config.validate_on_startup:
        return RedisTransportReadinessResult(
            status=RedisTransportReadinessStatus.DEGRADED,
            ready=False,
            validate_on_startup=False,
            ensure_stream_on_startup=transport_config.ensure_stream_on_startup,
            ensure_consumer_group_on_startup=(transport_config.ensure_consumer_group_on_startup),
            validation_performed=False,
            redis_reachable=False,
            stream_name=transport_config.stream_name,
            stream_ready=False,
            consumer_group_name=transport_config.consumer_group_name,
            consumer_group_ready=False,
            checked_at=checked_at,
            summary="Redis transport startup validation is disabled.",
        )

    client = create_redis_client()
    bootstrap_applied = False

    try:
        stream_exists = bool(client.exists(transport_config.stream_name))
        if apply_startup_policy and transport_config.ensure_stream_on_startup and not stream_exists:
            _ensure_redis_stream(client=client, stream_name=transport_config.stream_name)
            bootstrap_applied = True
            stream_exists = True

        groups = client.xinfo_groups(transport_config.stream_name) if stream_exists else []
        consumer_group_exists = any(
            str(group.get("name")) == transport_config.consumer_group_name for group in groups
        )
        if (
            apply_startup_policy
            and transport_config.ensure_consumer_group_on_startup
            and stream_exists
            and not consumer_group_exists
        ):
            ensure_redis_consumer_group(
                client=client,
                stream_name=transport_config.stream_name,
                consumer_group_name=transport_config.consumer_group_name,
            )
            bootstrap_applied = True
            groups = client.xinfo_groups(transport_config.stream_name)
            consumer_group_exists = any(
                str(group.get("name")) == transport_config.consumer_group_name for group in groups
            )
    except HTTPException:
        raise
    except (ResponseError, RedisError):
        return RedisTransportReadinessResult(
            status=RedisTransportReadinessStatus.UNAVAILABLE,
            ready=False,
            validate_on_startup=transport_config.validate_on_startup,
            ensure_stream_on_startup=transport_config.ensure_stream_on_startup,
            ensure_consumer_group_on_startup=(transport_config.ensure_consumer_group_on_startup),
            validation_performed=True,
            redis_reachable=False,
            stream_name=transport_config.stream_name,
            stream_ready=False,
            consumer_group_name=transport_config.consumer_group_name,
            consumer_group_ready=False,
            checked_at=checked_at,
            summary="Redis transport readiness could not reach Redis.",
        )

    ready = stream_exists and consumer_group_exists
    status = (
        RedisTransportReadinessStatus.READY if ready else RedisTransportReadinessStatus.DEGRADED
    )
    summary = _build_readiness_summary(
        stream_ready=stream_exists,
        consumer_group_ready=consumer_group_exists,
        bootstrap_applied=bootstrap_applied,
        startup_policy=apply_startup_policy,
    )
    return RedisTransportReadinessResult(
        status=status,
        ready=ready,
        validate_on_startup=transport_config.validate_on_startup,
        ensure_stream_on_startup=transport_config.ensure_stream_on_startup,
        ensure_consumer_group_on_startup=transport_config.ensure_consumer_group_on_startup,
        validation_performed=True,
        bootstrap_applied=bootstrap_applied,
        redis_reachable=True,
        stream_name=transport_config.stream_name,
        stream_ready=stream_exists,
        consumer_group_name=transport_config.consumer_group_name,
        consumer_group_ready=consumer_group_exists,
        checked_at=checked_at,
        summary=summary,
    )


def _ensure_redis_stream(*, client, stream_name: str) -> None:
    message_id = client.xadd(stream_name, {"bootstrap": "startup"})
    client.xdel(stream_name, message_id)


def _build_readiness_summary(
    *,
    stream_ready: bool,
    consumer_group_ready: bool,
    bootstrap_applied: bool,
    startup_policy: bool,
) -> str:
    if stream_ready and consumer_group_ready:
        if bootstrap_applied and startup_policy:
            return "Redis transport readiness is satisfied after bounded startup bootstrap."
        return "Redis transport readiness is satisfied."
    if not stream_ready:
        return "Redis transport readiness is degraded because the dispatch stream is missing."
    return "Redis transport readiness is degraded because the consumer group is missing."


def get_redis_transport_startup_readiness_snapshot(
    app: FastAPI,
) -> RedisTransportReadinessResult:
    snapshot = getattr(app.state, "redis_transport_startup_readiness", None)
    if isinstance(snapshot, RedisTransportReadinessResult):
        return snapshot
    return evaluate_redis_transport_readiness(apply_startup_policy=True)
