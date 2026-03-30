from __future__ import annotations

import json

from app.runtime.contracts import QueueBackendMessageEnvelope, RedisDispatchClaimedMessage


def build_dispatch_stream_fields(
    *,
    envelope: QueueBackendMessageEnvelope,
    dispatch_request_identity: str,
) -> dict[str, str]:
    return {
        "backend_name": envelope.backend_name,
        "message_type": envelope.message_type,
        "payload_version": envelope.payload_version.value,
        "dispatch_category": envelope.dispatch_category.value,
        "dispatch_request_identity": dispatch_request_identity,
        "routing_key": str(envelope.envelope_body.get("routing_key", "")),
        "source_identifiers": json.dumps(envelope.source_identifiers, sort_keys=True),
        "correlation_lineage": json.dumps(envelope.correlation_lineage, sort_keys=True),
        "dispatch_metadata": json.dumps(envelope.dispatch_metadata, sort_keys=True),
        "intended_worker_path": envelope.intended_worker_path,
        "body": json.dumps(envelope.envelope_body.get("body", {}), sort_keys=True),
    }


def parse_dispatch_stream_message(
    *,
    message_id: str,
    fields: dict[str, str],
    claimed_at: str,
    delivery_count: int,
) -> RedisDispatchClaimedMessage:
    return RedisDispatchClaimedMessage(
        message_id=message_id,
        dispatch_request_identity=str(fields.get("dispatch_request_identity", "")),
        dispatch_category=str(fields.get("dispatch_category", "")),
        payload_version=str(fields.get("payload_version", "")),
        intended_worker_path=str(fields.get("intended_worker_path", "")),
        source_identifiers=_parse_json_dict(fields.get("source_identifiers")),
        correlation_lineage=_parse_json_dict(fields.get("correlation_lineage")),
        dispatch_metadata=_parse_json_dict(fields.get("dispatch_metadata")),
        body=_parse_json_dict(fields.get("body")),
        delivery_count=delivery_count,
        claimed_at=claimed_at,
    )


def _parse_json_dict(raw_value: str | None) -> dict[str, object]:
    if not raw_value:
        return {}
    loaded = json.loads(raw_value)
    if isinstance(loaded, dict):
        return loaded
    return {}
