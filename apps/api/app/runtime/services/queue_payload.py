from __future__ import annotations

from app.runtime.contracts import QueueEnqueuePayload, QueuePayloadVersion
from app.runtime.schemas import DerivedWorkDispatchRequestProjection


def build_queue_enqueue_payload(
    dispatch_request: DerivedWorkDispatchRequestProjection,
) -> QueueEnqueuePayload:
    lineage = dispatch_request.lineage
    serialized_payload = {
        "payload_version": QueuePayloadVersion.V1.value,
        "dispatch_category": dispatch_request.dispatch_category.value,
        "source": {
            "job_run_id": dispatch_request.source_job_run_id,
            "command_id": lineage.source_command_id if lineage else None,
            "attempt_id": lineage.source_attempt_id if lineage else None,
            "source_correlation_id": dispatch_request.lineage.source_correlation_id if lineage else None,
            "derived_correlation_id": dispatch_request.derived_correlation_id,
        },
        "dispatch_metadata": dispatch_request.dispatch_ready_metadata,
        "intended_worker_path": dispatch_request.intended_path,
    }
    return QueueEnqueuePayload(
        dispatch_category=dispatch_request.dispatch_category,
        source_job_run_id=dispatch_request.source_job_run_id,
        source_command_id=lineage.source_command_id if lineage else None,
        source_attempt_id=lineage.source_attempt_id if lineage else None,
        lineage=lineage,
        source_correlation_id=lineage.source_correlation_id if lineage else None,
        derived_correlation_id=dispatch_request.derived_correlation_id,
        dispatch_metadata=dispatch_request.dispatch_ready_metadata,
        intended_worker_path=dispatch_request.intended_path,
        serialized_payload=serialized_payload,
    )
