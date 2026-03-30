from __future__ import annotations

from fastapi import HTTPException, status
from redis.exceptions import RedisError, ResponseError

from app.runtime.contracts import (
    RedisTransportStatusLevel,
    RedisTransportStatusResult,
)
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_transport import get_redis_transport_config
from app.runtime.schemas import RedisTransportStatusRequest


def get_redis_transport_status(
    payload: RedisTransportStatusRequest,
) -> RedisTransportStatusResult:
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group_name = transport_config.consumer_group_name

    try:
        stream_exists = bool(client.exists(stream_name))
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport status.",
        ) from exc

    if not stream_exists:
        return RedisTransportStatusResult(
            status=RedisTransportStatusLevel.DEGRADED,
            ready=False,
            stream_name=stream_name,
            stream_exists=False,
            stream_depth=0,
            consumer_group_name=consumer_group_name,
            consumer_group_exists=False,
            stale_threshold_ms=payload.stale_threshold_ms,
            summary="Redis dispatch stream is missing.",
        )

    try:
        stream_depth = int(client.xlen(stream_name))
        groups = client.xinfo_groups(stream_name)
    except ResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport status.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport status.",
        ) from exc

    group_info = next(
        (group for group in groups if str(group.get("name")) == consumer_group_name),
        None,
    )
    if group_info is None:
        return RedisTransportStatusResult(
            status=RedisTransportStatusLevel.DEGRADED,
            ready=False,
            stream_name=stream_name,
            stream_exists=True,
            stream_depth=stream_depth,
            consumer_group_name=consumer_group_name,
            consumer_group_exists=False,
            stale_threshold_ms=payload.stale_threshold_ms,
            summary="Redis consumer group is missing for the dispatch stream.",
        )

    pending_count = int(group_info.get("pending", 0))
    consumer_count = int(group_info.get("consumers", 0))
    lag = _coerce_int(group_info.get("lag"))
    pending_entries = []
    if pending_count:
        try:
            pending_entries = client.xpending_range(
                stream_name,
                consumer_group_name,
                min="-",
                max="+",
                count=min(payload.pending_sample_count, pending_count),
            )
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                return RedisTransportStatusResult(
                    status=RedisTransportStatusLevel.DEGRADED,
                    ready=False,
                    stream_name=stream_name,
                    stream_exists=True,
                    stream_depth=stream_depth,
                    consumer_group_name=consumer_group_name,
                    consumer_group_exists=False,
                    stale_threshold_ms=payload.stale_threshold_ms,
                    summary="Redis consumer group is missing for the dispatch stream.",
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis queue backend is unavailable for transport status.",
            ) from exc
        except RedisError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis queue backend is unavailable for transport status.",
            ) from exc

    inspected_pending_count = len(pending_entries)
    idle_values = [int(entry["time_since_delivered"]) for entry in pending_entries]
    stale_pending_count = sum(1 for idle_ms in idle_values if idle_ms >= payload.stale_threshold_ms)
    oldest_pending_idle_ms = max(idle_values) if idle_values else None
    ready = consumer_count > 0 and stale_pending_count == 0
    status_level = RedisTransportStatusLevel.READY if ready else RedisTransportStatusLevel.DEGRADED
    summary = _build_status_summary(
        consumer_count=consumer_count,
        pending_count=pending_count,
        stale_pending_count=stale_pending_count,
    )

    return RedisTransportStatusResult(
        status=status_level,
        ready=ready,
        stream_name=stream_name,
        stream_exists=True,
        stream_depth=stream_depth,
        consumer_group_name=consumer_group_name,
        consumer_group_exists=True,
        consumer_count=consumer_count,
        pending_count=pending_count,
        inspected_pending_count=inspected_pending_count,
        stale_pending_count=stale_pending_count,
        oldest_pending_idle_ms=oldest_pending_idle_ms,
        stale_threshold_ms=payload.stale_threshold_ms,
        lag=lag,
        summary=summary,
    )


def _build_status_summary(
    *,
    consumer_count: int,
    pending_count: int,
    stale_pending_count: int,
) -> str:
    if consumer_count <= 0:
        return "Redis transport is degraded because no active consumers are registered."
    if stale_pending_count > 0:
        return "Redis transport is degraded because stale pending dispatch messages were detected."
    if pending_count > 0:
        return "Redis transport is ready with pending dispatch messages awaiting completion."
    return "Redis transport is ready."


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
