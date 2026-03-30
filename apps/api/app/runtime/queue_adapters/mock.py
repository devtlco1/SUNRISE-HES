from __future__ import annotations

import uuid

from app.runtime.contracts import (
    DerivedWorkDispatchCategory,
    DerivedWorkEnqueueCategory,
    QueueEnqueuePayload,
    QueueEnqueueResult,
    QueueEnqueueStatus,
)


class MockQueueAdapter:
    def enqueue(self, payload: QueueEnqueuePayload) -> QueueEnqueueResult:
        enqueue_category = _map_dispatch_to_enqueue_category(payload.dispatch_category)
        receipt_namespace = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{payload.source_job_run_id}:{payload.dispatch_category.value}",
        )
        return QueueEnqueueResult(
            enqueue_category=enqueue_category,
            dispatch_request_identity=f"{payload.source_job_run_id}:{payload.dispatch_category.value}",
            source_job_run_id=payload.source_job_run_id,
            lineage=payload.lineage,
            derived_correlation_id=payload.derived_correlation_id,
            adapter_receipt_id=f"mock-receipt:{receipt_namespace}",
            enqueue_status=QueueEnqueueStatus.ACCEPTED,
            enqueue_metadata={
                "adapter": "mock_queue_adapter",
                "payload_version": payload.payload_version.value,
                "dispatch_category": payload.dispatch_category.value,
                "dispatch_metadata": payload.dispatch_metadata,
                "serialized_payload": payload.serialized_payload,
            },
            intended_path=payload.intended_worker_path,
        )


def _map_dispatch_to_enqueue_category(
    dispatch_category: DerivedWorkDispatchCategory,
) -> DerivedWorkEnqueueCategory:
    if dispatch_category == DerivedWorkDispatchCategory.RETRY_DISPATCH_REQUEST:
        return DerivedWorkEnqueueCategory.RETRY_ENQUEUE_RESULT
    return DerivedWorkEnqueueCategory.FOLLOWUP_ENQUEUE_RESULT
