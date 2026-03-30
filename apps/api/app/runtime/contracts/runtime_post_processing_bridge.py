from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum
from app.runtime.contracts.postprocessing import RuntimeDownstreamSignals
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage


class RuntimePostProcessingBridgeStatus(StringEnum):
    BRIDGED = "bridged"


class RuntimePostProcessingBridgeResult(BaseModel):
    status: RuntimePostProcessingBridgeStatus
    post_processing_record_id: str
    session_identifier: str
    disposition_record_id: str
    outcome_record_id: str
    executor_identifier: str
    job_run_id: str
    related_command_id: str
    command_attempt_id: str
    terminal_outcome: str
    downstream_state: str
    post_processing_recorded_at: str
    post_processing_recorded_by_executor_identifier: str
    post_processing_reason: str | None = None
    signals: RuntimeDownstreamSignals
    already_recorded: bool = False
    summary: str
    lineage: RuntimeExecutionSessionLineage
