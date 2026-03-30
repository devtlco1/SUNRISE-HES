from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.downstream import DerivedWorkDispatchCategory, DerivedWorkLineage


class QueuePayloadVersion(StringEnum):
    V1 = "v1"


class QueueAdapterCapabilities(BaseModel):
    supports_priority: bool = False
    supports_delay: bool = False
    supports_receipts: bool = False
    supports_deduplication: bool = False
    supports_visibility_timeout: bool = False


class QueueEnqueuePayload(BaseModel):
    payload_version: QueuePayloadVersion = QueuePayloadVersion.V1
    dispatch_category: DerivedWorkDispatchCategory
    source_job_run_id: str
    source_command_id: str | None = None
    source_attempt_id: str | None = None
    lineage: DerivedWorkLineage | None = None
    source_correlation_id: str | None = None
    derived_correlation_id: str | None = None
    dispatch_metadata: dict[str, object]
    intended_worker_path: str
    serialized_payload: dict[str, object] = Field(default_factory=dict)


class QueueBackendMessageEnvelope(BaseModel):
    backend_name: str
    message_type: str
    payload_version: QueuePayloadVersion
    dispatch_category: DerivedWorkDispatchCategory
    source_identifiers: dict[str, str | None]
    correlation_lineage: dict[str, str | None]
    dispatch_metadata: dict[str, object]
    intended_worker_path: str
    envelope_body: dict[str, object]
