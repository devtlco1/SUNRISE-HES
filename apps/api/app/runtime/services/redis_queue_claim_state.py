from __future__ import annotations

from fastapi import HTTPException, status
from redis.exceptions import RedisError, ResponseError

from app.runtime.redis_client import create_redis_client
from app.runtime.redis_queue_worker import build_worker_consumer_name, claim_token_matches
from app.runtime.redis_transport import get_redis_transport_config


def load_pending_redis_dispatch_claim(
    *,
    worker_identifier: str,
    message_id: str,
    claim_token: str,
    include_fields: bool = False,
) -> dict[str, object]:
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group = transport_config.consumer_group_name
    consumer_name = build_worker_consumer_name(worker_identifier)
    if not claim_token_matches(
        claim_token=claim_token,
        consumer_name=consumer_name,
        message_id=message_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claim token is invalid for the requested dispatch message.",
        )

    try:
        if not client.exists(stream_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch stream does not exist.",
            )
        pending_entries = client.xpending_range(
            stream_name,
            consumer_group,
            min=message_id,
            max=message_id,
            count=1,
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
            detail="Redis queue backend is unavailable for dispatch claim validation.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch claim validation.",
        ) from exc

    if not pending_entries:
        stream_entries = client.xrange(stream_name, min=message_id, max=message_id, count=1)
        if not stream_entries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch message does not exist.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message is not in a valid pending state.",
        )

    pending_entry = pending_entries[0]
    if str(pending_entry["consumer"]) != consumer_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message belongs to a different consumer.",
        )

    result: dict[str, object] = {
        "stream_name": stream_name,
        "consumer_group": consumer_group,
        "consumer_name": consumer_name,
        "pending_entry": pending_entry,
    }
    if include_fields:
        stream_entries = client.xrange(stream_name, min=message_id, max=message_id, count=1)
        if not stream_entries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch message does not exist.",
            )
        _, fields = stream_entries[0]
        result["fields"] = fields
    return result
