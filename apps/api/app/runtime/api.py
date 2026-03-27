import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.jobs.dependencies import require_internal_api_token
from app.runtime.contracts import ProtocolExecutionPlan
from app.runtime.schemas import ExecuteRuntimePlanRequest, ExecuteRuntimePlanResponse
from app.runtime.services import build_runtime_plan_for_command, execute_runtime_plan_for_attempt

internal_runtime_router = APIRouter(prefix="/internal/commands", tags=["internal-runtime"])
internal_runtime_attempts_router = APIRouter(
    prefix="/internal/command-attempts",
    tags=["internal-runtime-attempts"],
)


@internal_runtime_router.post(
    "/{command_id}/build-runtime-plan",
    response_model=ProtocolExecutionPlan,
    dependencies=[Depends(require_internal_api_token)],
)
def build_runtime_plan_endpoint(
    command_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_db_session),
) -> ProtocolExecutionPlan:
    request_context = getattr(request.state, "request_audit_context", None)
    request_id = getattr(request_context, "request_id", None)
    return build_runtime_plan_for_command(
        session,
        command_id=command_id,
        request_id=request_id,
    )


@internal_runtime_attempts_router.post(
    "/{attempt_id}/execute-runtime-plan",
    response_model=ExecuteRuntimePlanResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def execute_runtime_plan_endpoint(
    attempt_id: uuid.UUID,
    payload: ExecuteRuntimePlanRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> ExecuteRuntimePlanResponse:
    request_context = getattr(request.state, "request_audit_context", None)
    request_id = getattr(request_context, "request_id", None)
    return execute_runtime_plan_for_attempt(
        session,
        attempt_id=attempt_id,
        worker_identifier=payload.worker_identifier,
        request_id=request_id,
    )
