from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeOperationalClosureStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeOperationalClosureResult(BaseModel):
    status: RuntimeOperationalClosureStatus
    closure_record_id: str
    session_identifier: str
    materialization_record_id: str
    post_processing_record_id: str
    disposition_record_id: str
    outcome_record_id: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    terminal_outcome: str
    downstream_state: str
    included_follow_up_descriptor_types: list[str] = Field(default_factory=list)
    closure_recorded_at: str
    closure_recorded_by_executor_identifier: str
    closure_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
