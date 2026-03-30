from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from redis.exceptions import RedisError, ResponseError

from app.runtime.contracts import (
    RedisClaimContract,
    RedisDispatchPendingEntry,
    RedisDispatchPendingInspectionResult,
    RedisDispatchRecoveryResult,
    RedisDispatchRecoveryStatus,
)
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_dispatch_stream import parse_dispatch_stream_message
from app.runtime.redis_queue_worker import build_claim_token, build_worker_consumer_name
from app.runtime.redis_transport import get_redis_transport_config
from app.runtime.schemas import (
    RedisDispatchPendingInspectionRequest,
    RedisDispatchRecoveryRequest,
)


def inspect_pending_redis_dispatch_messages(
    payload: RedisDispatchPendingInspectionRequest,
) -> RedisDispatchPendingInspectionResult:
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group = transport_config.consumer_group_name
    pending_entries = _load_pending_entries(
        client=client,
        stream_name=stream_name,
        consumer_group=consumer_group,
        message_id=payload.message_id,
        count=payload.count,
    )

    items: list[RedisDispatchPendingEntry] = []
    for pending_entry in pending_entries:
        message_id = str(pending_entry["message_id"])
        stream_fields = _load_stream_fields(
            client=client,
            stream_name=stream_name,
            message_id=message_id,
        )
        idle_ms = int(pending_entry["time_since_delivered"])
        items.append(
            RedisDispatchPendingEntry(
                message_id=message_id,
                consumer_name=str(pending_entry["consumer"]),
                idle_ms=idle_ms,
                delivery_count=int(pending_entry["times_delivered"]),
                stale=idle_ms >= payload.stale_threshold_ms,
                dispatch_request_identity=str(stream_fields.get("dispatch_request_identity", "")),
                dispatch_category=str(stream_fields.get("dispatch_category", "")),
                intended_worker_path=str(stream_fields.get("intended_worker_path", "")),
            )
        )

    return RedisDispatchPendingInspectionResult(
        stream_name=stream_name,
        consumer_group=consumer_group,
        stale_threshold_ms=payload.stale_threshold_ms,
        total_entries=len(items),
        items=items,
    )


def recover_stale_redis_dispatch_message(
    payload: RedisDispatchRecoveryRequest,
) -> RedisDispatchRecoveryResult:
    client = create_redis_client()
    transport_config = get_redis_transport_config()
    stream_name = transport_config.stream_name
    consumer_group = transport_config.consumer_group_name
    consumer_name = build_worker_consumer_name(payload.worker_identifier)
    pending_entry = _load_pending_entry(
        client=client,
        stream_name=stream_name,
        consumer_group=consumer_group,
        message_id=payload.message_id,
    )
    idle_ms = int(pending_entry["time_since_delivered"])
    if idle_ms < payload.stale_threshold_ms:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Redis dispatch message is not stale enough for recovery.",
        )

    try:
        claimed_entries = client.xclaim(
            stream_name,
            consumer_group,
            consumer_name,
            min_idle_time=payload.stale_threshold_ms,
            message_ids=[payload.message_id],
        )
    except ResponseError as exc:
        if "NOGROUP" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Redis consumer group is not initialized for the dispatch stream.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch recovery.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch recovery.",
        ) from exc

    if not claimed_entries:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Redis dispatch message could not be reclaimed from the pending state.",
        )

    _, fields = claimed_entries[0]
    recovered_at = datetime.now(UTC).isoformat()
    delivery_count = int(pending_entry["times_delivered"]) + 1
    claim_timeout_seconds = transport_config.claim_timeout_seconds
    claim_token = build_claim_token(
        consumer_group=consumer_group,
        consumer_name=consumer_name,
        message_id=payload.message_id,
        claim_timeout_seconds=claim_timeout_seconds,
    )

    return RedisDispatchRecoveryResult(
        status=RedisDispatchRecoveryStatus.RECLAIMED,
        stream_name=stream_name,
        consumer_group=consumer_group,
        consumer_name=consumer_name,
        original_consumer_name=str(pending_entry["consumer"]),
        message_id=payload.message_id,
        stale_threshold_ms=payload.stale_threshold_ms,
        idle_ms=idle_ms,
        delivery_count=delivery_count,
        claim=RedisClaimContract(
            pending_message_id=payload.message_id,
            claim_token=claim_token,
            consumer_name=consumer_name,
            claim_timeout_seconds=claim_timeout_seconds,
        ),
        recovery_receipt_id=(
            f"redis-recovery:{consumer_group}:{consumer_name}:{payload.message_id}"
        ),
        recovered_at=recovered_at,
        message=parse_dispatch_stream_message(
            message_id=payload.message_id,
            fields=fields,
            claimed_at=recovered_at,
            delivery_count=delivery_count,
        ),
    )


def _load_pending_entries(
    *,
    client,
    stream_name: str,
    consumer_group: str,
    message_id: str | None,
    count: int,
) -> list[dict[str, object]]:
    try:
        if not client.exists(stream_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Redis dispatch stream does not exist.",
            )
        min_id = message_id or "-"
        max_id = message_id or "+"
        pending_entries = client.xpending_range(
            stream_name,
            consumer_group,
            min=min_id,
            max=max_id,
            count=count,
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
            detail="Redis queue backend is unavailable for dispatch recovery.",
        ) from exc
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch recovery.",
        ) from exc
    return pending_entries


def _load_pending_entry(
    *,
    client,
    stream_name: str,
    consumer_group: str,
    message_id: str,
) -> dict[str, object]:
    pending_entries = _load_pending_entries(
        client=client,
        stream_name=stream_name,
        consumer_group=consumer_group,
        message_id=message_id,
        count=1,
    )
    if pending_entries:
        return pending_entries[0]

    stream_entries = _load_stream_entries(
        client=client,
        stream_name=stream_name,
        message_id=message_id,
    )
    if not stream_entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redis dispatch message does not exist.",
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Redis dispatch message is not currently pending.",
    )


def _load_stream_fields(*, client, stream_name: str, message_id: str) -> dict[str, str]:
    stream_entries = _load_stream_entries(
        client=client,
        stream_name=stream_name,
        message_id=message_id,
    )
    if not stream_entries:
        return {}
    _, fields = stream_entries[0]
    return fields


def _load_stream_entries(*, client, stream_name: str, message_id: str):
    try:
        return client.xrange(stream_name, min=message_id, max=message_id, count=1)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for dispatch recovery.",
        ) from exc
