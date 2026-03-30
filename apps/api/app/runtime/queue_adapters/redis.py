from __future__ import annotations

from fastapi import HTTPException, status
from redis.exceptions import RedisError

from app.runtime.contracts import (
    DerivedWorkDispatchCategory,
    DerivedWorkEnqueueCategory,
    QueueEnqueuePayload,
    QueueEnqueueResult,
    QueueEnqueueStatus,
)
from app.runtime.queue_serializers import RedisQueueSerializer
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_dispatch_stream import build_dispatch_stream_fields
from app.runtime.redis_transport import get_redis_transport_config


class RedisQueueAdapter:
    def __init__(self) -> None:
        self._client = None
        transport_config = get_redis_transport_config()
        self._serializer = RedisQueueSerializer(stream_name=transport_config.stream_name)

    def enqueue(self, payload: QueueEnqueuePayload) -> QueueEnqueueResult:
        enqueue_category = _map_dispatch_to_enqueue_category(payload.dispatch_category)
        dispatch_request_identity = f"{payload.source_job_run_id}:{payload.dispatch_category.value}"
        envelope = self._serializer.serialize(payload)
        stream_name = str(envelope.envelope_body["stream"])
        published_fields = build_dispatch_stream_fields(
            envelope=envelope,
            dispatch_request_identity=dispatch_request_identity,
        )

        try:
            message_id = str(self._get_client().xadd(stream_name, fields=published_fields))
        except RedisError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis queue backend is unavailable for dispatch enqueue.",
            ) from exc

        return QueueEnqueueResult(
            enqueue_category=enqueue_category,
            dispatch_request_identity=dispatch_request_identity,
            source_job_run_id=payload.source_job_run_id,
            lineage=payload.lineage,
            derived_correlation_id=payload.derived_correlation_id,
            adapter_receipt_id=f"redis-receipt:{message_id}",
            enqueue_status=QueueEnqueueStatus.ACCEPTED,
            enqueue_metadata={
                "adapter": "redis_queue_adapter",
                "payload_version": payload.payload_version.value,
                "dispatch_category": payload.dispatch_category.value,
                "dispatch_metadata": payload.dispatch_metadata,
                "serialized_payload": payload.serialized_payload,
                "backend_message_envelope": envelope.model_dump(mode="json"),
                "redis_stream_name": stream_name,
                "redis_message_id": message_id,
                "publish_transport": "redis_stream",
            },
            intended_path=payload.intended_worker_path,
        )

    def _get_client(self):
        if self._client is None:
            self._client = create_redis_client()
        return self._client


def _map_dispatch_to_enqueue_category(
    dispatch_category: DerivedWorkDispatchCategory,
) -> DerivedWorkEnqueueCategory:
    if dispatch_category == DerivedWorkDispatchCategory.RETRY_DISPATCH_REQUEST:
        return DerivedWorkEnqueueCategory.RETRY_ENQUEUE_RESULT
    return DerivedWorkEnqueueCategory.FOLLOWUP_ENQUEUE_RESULT
