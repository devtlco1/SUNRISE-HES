from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeFollowUpMaterializationStatus(StringEnum):
    MATERIALIZED = "materialized"


class RuntimeFollowUpDescriptorType(StringEnum):
    TERMINAL_SUMMARY_READY = "terminal_summary_ready"
    AUDIT_PLACEHOLDER_READY = "audit_placeholder_ready"
    DOWNSTREAM_NOTIFICATION_PLACEHOLDER_READY = (
        "downstream_notification_placeholder_ready"
    )
    EXTERNALIZATION_PLACEHOLDER_READY = "externalization_placeholder_ready"


class RuntimeFollowUpDescriptor(BaseModel):
    descriptor_type: RuntimeFollowUpDescriptorType
    reason: str
    payload: dict[str, object] | None = None


class RuntimeFollowUpMaterializationResult(BaseModel):
    status: RuntimeFollowUpMaterializationStatus
    materialization_record_id: str
    session_identifier: str
    post_processing_record_id: str
    disposition_record_id: str
    outcome_record_id: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    terminal_outcome: str
    downstream_state: str
    follow_up_descriptors: list[RuntimeFollowUpDescriptor] = Field(default_factory=list)
    materialized_at: str
    materialized_by_executor_identifier: str
    materialization_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
