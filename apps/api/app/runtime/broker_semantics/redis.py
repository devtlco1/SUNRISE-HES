from __future__ import annotations

import uuid

from app.runtime.contracts import (
    QueueBackendMessageEnvelope,
    RedisQueueDeliveryContract,
    RedisQueueReceiptContract,
    RedisQueueSemantics,
)


def map_envelope_to_redis_semantics(
    envelope: QueueBackendMessageEnvelope,
) -> RedisQueueSemantics:
    job_run_id = envelope.source_identifiers.get("job_run_id") or "unknown-job-run"
    routing_key = str(envelope.envelope_body.get("routing_key", envelope.dispatch_category.value))
    message_namespace = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"redis-envelope:{job_run_id}:{envelope.dispatch_category.value}",
    )
    delivery = RedisQueueDeliveryContract(
        stream_name=str(envelope.envelope_body.get("stream", "hes:dispatch")),
        consumer_group="hes-worker-group",
        routing_key=routing_key,
        claim_timeout_seconds=300,
        delivery_attempt=0,
        dead_letter_stream="hes:dispatch:dead-letter",
    )
    receipt = RedisQueueReceiptContract(
        message_id=f"redis-placeholder-message:{message_namespace}",
        receipt_id=f"redis-placeholder-receipt:{message_namespace}",
        ack_required=True,
    )
    return RedisQueueSemantics(
        delivery=delivery,
        receipt=receipt,
        metadata={
            "message_type": envelope.message_type,
            "payload_version": envelope.payload_version.value,
            "source_identifiers": envelope.source_identifiers,
            "correlation_lineage": envelope.correlation_lineage,
            "dispatch_metadata": envelope.dispatch_metadata,
            "intended_worker_path": envelope.intended_worker_path,
        },
    )
