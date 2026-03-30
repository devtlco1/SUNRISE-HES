from __future__ import annotations

from fastapi import HTTPException, status
from redis.exceptions import RedisError, ResponseError

from app.runtime.contracts import (
    RedisTransportAdminAction,
    RedisTransportAdminResult,
    RedisTransportAdminStatus,
)
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_transport import get_redis_transport_config
from app.runtime.schemas import (
    RedisConsumerGroupBootstrapRequest,
    RedisConsumerGroupResetRequest,
)


def bootstrap_redis_consumer_group(
    payload: RedisConsumerGroupBootstrapRequest,
) -> RedisTransportAdminResult:
    del payload
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group_name = transport_config.consumer_group_name
    overview = _load_group_overview(
        client=client,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
    )
    if not overview["stream_exists"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redis dispatch stream does not exist.",
        )

    if overview["consumer_group_exists"]:
        return RedisTransportAdminResult(
            action=RedisTransportAdminAction.BOOTSTRAP_CONSUMER_GROUP,
            status=RedisTransportAdminStatus.ALREADY_EXISTS,
            stream_name=stream_name,
            consumer_group_name=consumer_group_name,
            stream_exists=True,
            consumer_group_exists_before=True,
            consumer_group_exists_after=True,
            consumer_count_before=overview["consumer_count"],
            pending_count_before=overview["pending_count"],
            summary="Redis consumer group already exists for the dispatch stream.",
        )

    try:
        client.xgroup_create(
            name=stream_name,
            groupname=consumer_group_name,
            id="0",
            mkstream=False,
        )
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            return RedisTransportAdminResult(
                action=RedisTransportAdminAction.BOOTSTRAP_CONSUMER_GROUP,
                status=RedisTransportAdminStatus.ALREADY_EXISTS,
                stream_name=stream_name,
                consumer_group_name=consumer_group_name,
                stream_exists=True,
                consumer_group_exists_before=True,
                consumer_group_exists_after=True,
                consumer_count_before=overview["consumer_count"],
                pending_count_before=overview["pending_count"],
                summary="Redis consumer group already exists for the dispatch stream.",
            )
        if "requires the key to exist" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch stream does not exist.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport administration.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport administration.",
        ) from exc

    return RedisTransportAdminResult(
        action=RedisTransportAdminAction.BOOTSTRAP_CONSUMER_GROUP,
        status=RedisTransportAdminStatus.CREATED,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
        stream_exists=True,
        consumer_group_exists_before=False,
        consumer_group_exists_after=True,
        consumer_count_before=overview["consumer_count"],
        pending_count_before=overview["pending_count"],
        summary="Redis consumer group was created for the dispatch stream.",
    )


def reset_redis_consumer_group(
    payload: RedisConsumerGroupResetRequest,
) -> RedisTransportAdminResult:
    if not payload.confirm_destructive_action:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Redis consumer-group reset requires explicit destructive confirmation.",
        )

    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group_name = transport_config.consumer_group_name
    overview = _load_group_overview(
        client=client,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
    )
    if not overview["stream_exists"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redis dispatch stream does not exist.",
        )
    if not overview["consumer_group_exists"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Redis consumer group is not initialized for the dispatch stream.",
        )
    if overview["pending_count"] > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Redis consumer-group reset is refused while pending dispatch messages exist.",
        )

    try:
        destroyed = int(client.xgroup_destroy(stream_name, consumer_group_name))
        if destroyed != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Redis consumer group could not be reset safely.",
            )
        client.xgroup_create(
            name=stream_name,
            groupname=consumer_group_name,
            id="0",
            mkstream=False,
        )
    except HTTPException:
        raise
    except ResponseError as exc:
        if "requires the key to exist" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch stream does not exist.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport administration.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport administration.",
        ) from exc

    return RedisTransportAdminResult(
        action=RedisTransportAdminAction.RESET_CONSUMER_GROUP,
        status=RedisTransportAdminStatus.RESET,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
        stream_exists=True,
        consumer_group_exists_before=True,
        consumer_group_exists_after=True,
        consumer_count_before=overview["consumer_count"],
        pending_count_before=overview["pending_count"],
        summary="Redis consumer group was reset for the dispatch stream.",
    )


def ensure_redis_consumer_group(
    *,
    client,
    stream_name: str,
    consumer_group_name: str,
) -> None:
    try:
        client.xgroup_create(
            name=stream_name,
            groupname=consumer_group_name,
            id="0",
            mkstream=False,
        )
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            return
        if "requires the key to exist" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch stream does not exist.",
            ) from exc
        raise


def _load_group_overview(
    *,
    client,
    stream_name: str,
    consumer_group_name: str,
) -> dict[str, int | bool]:
    try:
        stream_exists = bool(client.exists(stream_name))
        if not stream_exists:
            return {
                "stream_exists": False,
                "consumer_group_exists": False,
                "consumer_count": 0,
                "pending_count": 0,
            }
        groups = client.xinfo_groups(stream_name)
    except ResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport administration.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for transport administration.",
        ) from exc

    group_info = next(
        (group for group in groups if str(group.get("name")) == consumer_group_name),
        None,
    )
    if group_info is None:
        return {
            "stream_exists": True,
            "consumer_group_exists": False,
            "consumer_count": 0,
            "pending_count": 0,
        }
    return {
        "stream_exists": True,
        "consumer_group_exists": True,
        "consumer_count": int(group_info.get("consumers", 0)),
        "pending_count": int(group_info.get("pending", 0)),
    }
