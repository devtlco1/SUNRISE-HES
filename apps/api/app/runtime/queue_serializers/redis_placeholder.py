from __future__ import annotations

from app.runtime.contracts import QueueBackendMessageEnvelope, QueueEnqueuePayload


class RedisPlaceholderQueueSerializer:
    def serialize(self, payload: QueueEnqueuePayload) -> QueueBackendMessageEnvelope:
        source_identifiers = {
            "job_run_id": payload.source_job_run_id,
            "command_id": payload.source_command_id,
            "attempt_id": payload.source_attempt_id,
        }
        correlation_lineage = {
            "source_correlation_id": payload.source_correlation_id,
            "derived_correlation_id": payload.derived_correlation_id,
        }
        envelope_body = {
            "stream": "hes:dispatch",
            "routing_key": payload.dispatch_category.value,
            "body": payload.serialized_payload,
        }
        return QueueBackendMessageEnvelope(
            backend_name="redis_placeholder",
            message_type="derived_work_dispatch",
            payload_version=payload.payload_version,
            dispatch_category=payload.dispatch_category,
            source_identifiers=source_identifiers,
            correlation_lineage=correlation_lineage,
            dispatch_metadata=payload.dispatch_metadata,
            intended_worker_path=payload.intended_worker_path,
            envelope_body=envelope_body,
        )
