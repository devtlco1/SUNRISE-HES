from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeAttemptDispositionStatus(StringEnum):
    BRIDGED = "bridged"


class RuntimeAttemptDispositionResult(BaseModel):
    status: RuntimeAttemptDispositionStatus
    disposition_record_id: str
    session_identifier: str
    outcome_record_id: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    terminal_outcome: str
    mapped_attempt_status: str
    mapped_command_status: str
    mapped_job_run_status: str
    disposition_recorded_at: str
    disposition_recorded_by_executor_identifier: str
    disposition_reason: str | None = None
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
