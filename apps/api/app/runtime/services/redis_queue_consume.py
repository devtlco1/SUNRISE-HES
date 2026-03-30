from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from redis.exceptions import RedisError, ResponseError

from app.runtime.contracts import (
    RedisClaimContract,
    RedisDequeueContract,
    RedisDispatchClaimResult,
    RedisDispatchClaimStatus,
)
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_dispatch_stream import parse_dispatch_stream_message
from app.runtime.redis_queue_worker import (
    build_claim_token,
    build_worker_consumer_name,
)
from app.runtime.redis_transport import get_redis_transport_config
from app.runtime.schemas import RedisDispatchDequeueClaimRequest
from app.runtime.services.redis_queue_admin import ensure_redis_consumer_group


def dequeue_and_claim_redis_dispatch_message(
    payload: RedisDispatchDequeueClaimRequest,
) -> RedisDispatchClaimResult:
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group = transport_config.consumer_group_name
    consumer_name = build_worker_consumer_name(payload.worker_identifier)

    try:
        if not client.exists(stream_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch stream does not exist.",
            )
        if payload.ensure_consumer_group:
            ensure_redis_consumer_group(
                client=client,
                stream_name=stream_name,
                consumer_group_name=consumer_group,
            )
        messages = client.xreadgroup(
            groupname=consumer_group,
            consumername=consumer_name,
            streams={stream_name: ">"},
            count=1,
            block=payload.block_ms or None,
        )
    except HTTPException:
        raise
    except ResponseError as exc:
        if "NOGROUP" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Redis consumer group is not initialized for the dispatch stream.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch dequeue.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch dequeue.",
        ) from exc

    if not messages:
        return RedisDispatchClaimResult(
            status=RedisDispatchClaimStatus.EMPTY,
            stream_name=stream_name,
            consumer_group=consumer_group,
            consumer_name=consumer_name,
        )

    _, entries = messages[0]
    message_id, fields = entries[0]
    claimed_at = datetime.now(UTC)
    claim_timeout_seconds = transport_config.claim_timeout_seconds
    claim_token = build_claim_token(
        consumer_group=consumer_group,
        consumer_name=consumer_name,
        message_id=message_id,
        claim_timeout_seconds=claim_timeout_seconds,
    )
    dequeue = RedisDequeueContract(
        consumer_name=consumer_name,
        stream_name=stream_name,
        consumer_group=consumer_group,
        pending_message_id=message_id,
        claim_timeout_seconds=claim_timeout_seconds,
        delivery_count=1,
    )
    claim = RedisClaimContract(
        pending_message_id=message_id,
        claim_token=claim_token,
        consumer_name=consumer_name,
        claim_timeout_seconds=claim_timeout_seconds,
    )
    return RedisDispatchClaimResult(
        status=RedisDispatchClaimStatus.CLAIMED,
        stream_name=stream_name,
        consumer_group=consumer_group,
        consumer_name=consumer_name,
        dequeue=dequeue,
        claim=claim,
        message=parse_dispatch_stream_message(
            message_id=message_id,
            fields=fields,
            claimed_at=claimed_at.isoformat(),
            delivery_count=1,
        ),
    )
