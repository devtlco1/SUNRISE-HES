from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RuntimeExecutionSessionStatus(StringEnum):
    ACTIVE = "active"
    FINALIZED = "finalized"


class RuntimeExecutionSessionLineage(BaseModel):
    handoff_record_id: str | None = None
    lease_record_id: str | None = None
    invocation_record_id: str | None = None
    guard_record_id: str | None = None
    dispatch_request_identity: str
    queue_message_id: str
    claim_token: str
    source_identifiers: dict[str, str | None] = Field(default_factory=dict)
    correlation_lineage: dict[str, str | None] = Field(default_factory=dict)
    dispatch_metadata: dict[str, object] = Field(default_factory=dict)
    intended_worker_path: str


class RuntimeExecutionSessionResult(BaseModel):
    status: RuntimeExecutionSessionStatus
    session_identifier: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    session_started_at: str
    last_heartbeat_at: str
    session_expires_at: str
    reused_existing_session: bool = False
    heartbeat_refreshed: bool = False
    finalized_at: str | None = None
    finalized_by_executor_identifier: str | None = None
    finalize_reason: str | None = None
    summary: str
    lineage: RuntimeExecutionSessionLineage
