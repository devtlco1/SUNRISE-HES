from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeExecutionOutcomeStatus(StringEnum):
    RECORDED = "recorded"


class RuntimeExecutionOutcomeResult(BaseModel):
    status: RuntimeExecutionOutcomeStatus
    outcome_record_id: str
    session_identifier: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    terminal_outcome: str
    outcome_recorded_at: str
    outcome_recorded_by_executor_identifier: str
    finalize_reason: str | None = None
    outcome_reason: str | None = None
    summary_message: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
