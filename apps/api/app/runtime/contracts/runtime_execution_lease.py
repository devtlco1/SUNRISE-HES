from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RuntimeExecutionLeaseStatus(StringEnum):
    LEASED = "leased"


class RuntimeExecutionLeaseLineage(BaseModel):
    handoff_record_id: str | None = None
    dispatch_request_identity: str
    queue_message_id: str
    claim_token: str
    source_identifiers: dict[str, str | None] = Field(default_factory=dict)
    correlation_lineage: dict[str, str | None] = Field(default_factory=dict)
    dispatch_metadata: dict[str, object] = Field(default_factory=dict)
    intended_worker_path: str


class RuntimeExecutionLeaseResult(BaseModel):
    status: RuntimeExecutionLeaseStatus
    lease_record_id: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    leased_at: str
    lease_expires_at: str
    reused_existing_lease: bool = False
    summary: str
    lineage: RuntimeExecutionLeaseLineage
