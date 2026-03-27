from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.commands.schemas import CommandExecutionAttemptResponse
from app.modules.connectivity.schemas import ConnectivitySessionHistoryResponse
from app.runtime.contracts import ProtocolExecutionPlan, RuntimeCommandOutcome


class ExecuteRuntimePlanRequest(BaseModel):
    worker_identifier: str = Field(min_length=1, max_length=128)


class ExecuteRuntimePlanResponse(BaseModel):
    plan: ProtocolExecutionPlan
    attempt: CommandExecutionAttemptResponse
    session: ConnectivitySessionHistoryResponse
    outcome: RuntimeCommandOutcome
    result_summary: dict[str, object] | None = None
    response_snapshot: dict[str, object] | None = None
