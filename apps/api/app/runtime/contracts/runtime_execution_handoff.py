from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RuntimeExecutionHandoffStatus(StringEnum):
    HANDED_OFF = "handed_off"


class RuntimeExecutionHandoffLineage(BaseModel):
    dispatch_request_identity: str
    queue_message_id: str
    claim_token: str
    source_identifiers: dict[str, str | None] = Field(default_factory=dict)
    correlation_lineage: dict[str, str | None] = Field(default_factory=dict)
    dispatch_metadata: dict[str, object] = Field(default_factory=dict)
    intended_worker_path: str


class RuntimeExecutionHandoffResult(BaseModel):
    status: RuntimeExecutionHandoffStatus
    backend_name: str = "redis"
    handoff_record_id: str
    stream_name: str
    consumer_group: str
    consumer_name: str
    worker_identifier: str
    job_run_id: str
    related_command_id: str | None = None
    command_attempt_id: str | None = None
    handed_off_at: str
    job_run_claimed: bool
    command_materialized: bool
    attempt_started: bool
    summary: str
    lineage: RuntimeExecutionHandoffLineage
