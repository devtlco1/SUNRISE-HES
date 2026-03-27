from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.runtime.contracts import ProtocolExecutionPlan
from app.runtime.planning import resolve_protocol_execution_plan


def build_runtime_plan_for_command(
    session: Session,
    *,
    command_id: UUID,
    worker_identifier: str | None = None,
    request_id: str | None = None,
) -> ProtocolExecutionPlan:
    return resolve_protocol_execution_plan(
        session,
        command_id=command_id,
        worker_identifier=worker_identifier,
        request_id=request_id,
    )
