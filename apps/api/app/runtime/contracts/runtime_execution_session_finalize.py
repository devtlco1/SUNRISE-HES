from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimeExecutionSessionFinalizeStatus(StringEnum):
    FINALIZED = "finalized"


class RuntimeExecutionSessionFinalizeResult(BaseModel):
    status: RuntimeExecutionSessionFinalizeStatus
    session_identifier: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    session_started_at: str
    last_heartbeat_at: str
    session_expires_at: str
    finalized_at: str
    finalized_by_executor_identifier: str
    finalize_reason: str | None = None
    already_finalized: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
