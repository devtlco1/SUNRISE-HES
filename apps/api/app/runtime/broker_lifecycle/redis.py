from __future__ import annotations

import uuid

from app.runtime.contracts import (
    RedisAckContract,
    RedisClaimContract,
    RedisDequeueContract,
    RedisMessageLifecycleContract,
    RedisQueueSemantics,
    RedisRedeliveryContract,
)


def map_redis_semantics_to_lifecycle_contracts(
    semantics: RedisQueueSemantics,
) -> RedisMessageLifecycleContract:
    message_id = semantics.receipt.message_id
    consumer_group = semantics.delivery.consumer_group
    consumer_name = "hes-worker-placeholder"
    claim_timeout_seconds = semantics.delivery.claim_timeout_seconds
    claim_token = _build_token("claim", message_id)
    ack_token = _build_token("ack", semantics.receipt.receipt_id)

    dequeue = RedisDequeueContract(
        consumer_name=consumer_name,
        stream_name=semantics.delivery.stream_name,
        consumer_group=consumer_group,
        pending_message_id=message_id,
        claim_timeout_seconds=claim_timeout_seconds,
        delivery_count=semantics.delivery.delivery_attempt,
    )
    claim = RedisClaimContract(
        pending_message_id=message_id,
        claim_token=claim_token,
        consumer_name=consumer_name,
        claim_timeout_seconds=claim_timeout_seconds,
    )
    ack = RedisAckContract(
        message_id=message_id,
        receipt_id=semantics.receipt.receipt_id,
        ack_token=ack_token,
        consumer_group=consumer_group,
    )
    redelivery = RedisRedeliveryContract(
        message_id=message_id,
        redelivery_count=semantics.delivery.delivery_attempt,
        stale_claim_hint=False,
        retry_claim_hint=True,
        dead_letter_stream=semantics.delivery.dead_letter_stream,
    )
    return RedisMessageLifecycleContract(
        dequeue=dequeue,
        claim=claim,
        ack=ack,
        redelivery=redelivery,
        metadata={
            "backend_name": semantics.backend_name,
            "routing_key": semantics.delivery.routing_key,
            "correlation_lineage": semantics.metadata.get("correlation_lineage"),
            "source_identifiers": semantics.metadata.get("source_identifiers"),
        },
    )


def _build_token(prefix: str, identity: str) -> str:
    token = uuid.uuid5(uuid.NAMESPACE_URL, f"{prefix}:{identity}")
    return f"{prefix}-token:{token}"
