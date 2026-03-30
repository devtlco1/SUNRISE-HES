from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from redis.exceptions import RedisError, ResponseError

from app.runtime.contracts import (
    RedisDispatchAckResult,
    RedisDispatchAckStatus,
    RedisDispatchReleaseMode,
    RedisDispatchReleaseResult,
    RedisDispatchReleaseStatus,
)
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_queue_worker import build_worker_consumer_name
from app.runtime.redis_transport import get_redis_transport_config
from app.runtime.schemas import RedisDispatchAckRequest, RedisDispatchReleaseRequest
from app.runtime.services.redis_queue_claim_state import load_pending_redis_dispatch_claim


def ack_redis_dispatch_message(
    payload: RedisDispatchAckRequest,
) -> RedisDispatchAckResult:
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group = transport_config.consumer_group_name
    consumer_name = build_worker_consumer_name(payload.worker_identifier)
    load_pending_redis_dispatch_claim(
        worker_identifier=payload.worker_identifier,
        message_id=payload.message_id,
        claim_token=payload.claim_token,
    )
    acked_at = datetime.now(UTC).isoformat()

    try:
        acked_count = int(client.xack(stream_name, consumer_group, payload.message_id))
    except ResponseError as exc:
        if "NOGROUP" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Redis consumer group is not initialized for the dispatch stream.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch completion.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch completion.",
        ) from exc

    if acked_count != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message is not in a valid pending state for ack.",
        )

    return RedisDispatchAckResult(
        status=RedisDispatchAckStatus.ACKED,
        stream_name=stream_name,
        consumer_group=consumer_group,
        consumer_name=consumer_name,
        message_id=payload.message_id,
        claim_token=payload.claim_token,
        ack_receipt_id=(f"redis-ack:{consumer_group}:{consumer_name}:{payload.message_id}"),
        acked_at=acked_at,
    )


def release_redis_dispatch_message(
    payload: RedisDispatchReleaseRequest,
) -> RedisDispatchReleaseResult:
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group = transport_config.consumer_group_name
    consumer_name = build_worker_consumer_name(payload.worker_identifier)
    claim = load_pending_redis_dispatch_claim(
        worker_identifier=payload.worker_identifier,
        message_id=payload.message_id,
        claim_token=payload.claim_token,
        include_fields=True,
    )
    released_at = datetime.now(UTC).isoformat()
    release_fields = dict(claim["fields"])
    release_fields["released_from_message_id"] = payload.message_id
    release_fields["released_by_consumer"] = consumer_name
    release_fields["released_at"] = released_at
    if payload.reason:
        release_fields["release_reason"] = payload.reason

    try:
        pipeline = client.pipeline(transaction=True)
        pipeline.xadd(stream_name, release_fields)
        pipeline.xack(stream_name, consumer_group, payload.message_id)
        requeued_message_id, acked_count = pipeline.execute()
    except ResponseError as exc:
        if "NOGROUP" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Redis consumer group is not initialized for the dispatch stream.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch completion.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch completion.",
        ) from exc

    if int(acked_count) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message is not in a valid pending state for release.",
        )

    return RedisDispatchReleaseResult(
        status=RedisDispatchReleaseStatus.RELEASED,
        release_mode=RedisDispatchReleaseMode.REQUEUED_COPY,
        stream_name=stream_name,
        consumer_group=consumer_group,
        consumer_name=consumer_name,
        original_message_id=payload.message_id,
        requeued_message_id=str(requeued_message_id),
        claim_token=payload.claim_token,
        release_receipt_id=(
            f"redis-release:{consumer_group}:{consumer_name}:{payload.message_id}:"
            f"{requeued_message_id}"
        ),
        released_at=released_at,
    )
