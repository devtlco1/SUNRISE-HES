import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.service import record_audit_event
from app.modules.auth.dependencies import require_permission
from app.modules.commands.schemas import CommandExecutionAttemptResponse
from app.modules.jobs.dependencies import require_internal_api_token
from app.modules.jobs.schemas import (
    CommandAttemptFailRequest,
    CommandAttemptSucceedRequest,
    CommandAttemptTimeoutRequest,
    CommandCancelRequest,
    CommandCancelResponse,
    JobDefinitionCreate,
    JobDefinitionListResponse,
    JobDefinitionResponse,
    JobDefinitionTargetAssignmentCreate,
    JobDefinitionTargetAssignmentListResponse,
    JobDefinitionTargetAssignmentResponse,
    JobDefinitionUpdate,
    GenerateDueRunsRequest,
    GenerateDueRunsResponse,
    JobRunCompleteRequest,
    JobRunFailRequest,
    JobRunListResponse,
    JobRunResponse,
    MaterializeCommandResponse,
    MarkCommandAttemptRunningRequest,
    ManualJobRunCreate,
    PrepareJobRunForExecutionRequest,
    PrepareJobRunForExecutionResponse,
    StartCommandAttemptRequest,
    WorkerClaimRequest,
    WorkerClaimResponse,
    WorkerLeaseRenewRequest,
)
from app.modules.jobs.service import (
    cancel_command,
    claim_job_runs,
    complete_job_run,
    create_job_definition,
    create_manual_job_run,
    assign_job_definition_target,
    fail_command_attempt,
    fail_job_run,
    get_job_definition,
    get_job_run,
    generate_due_runs,
    list_job_definitions,
    list_job_definition_targets,
    list_job_runs,
    materialize_job_run_command,
    mark_command_attempt_running,
    prepare_job_run_for_execution,
    renew_job_run_claim,
    serialize_job_definition,
    serialize_job_definition_target,
    serialize_job_run,
    start_command_attempt,
    succeed_command_attempt,
    timeout_command_attempt,
    update_job_definition,
)
from app.modules.users.models import User

job_definitions_router = APIRouter(prefix="/job-definitions", tags=["job-definitions"])
job_runs_router = APIRouter(prefix="/job-runs", tags=["job-runs"])
command_control_router = APIRouter(prefix="/commands", tags=["command-control"])
internal_job_runs_router = APIRouter(prefix="/internal/job-runs", tags=["internal-job-runs"])
internal_scheduler_router = APIRouter(prefix="/internal/scheduler", tags=["internal-scheduler"])
internal_command_attempts_router = APIRouter(
    prefix="/internal/command-attempts",
    tags=["internal-command-attempts"],
)


@job_definitions_router.get("", response_model=JobDefinitionListResponse)
def list_job_definitions_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("jobs.read")),
) -> JobDefinitionListResponse:
    return list_job_definitions(session)


@job_definitions_router.post("", response_model=JobDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_job_definition_endpoint(
    payload: JobDefinitionCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("jobs.write")),
) -> JobDefinitionResponse:
    job_definition = create_job_definition(session, payload)
    response = serialize_job_definition(job_definition)
    record_audit_event(
        session,
        action="jobs.definitions.create",
        resource_type="jobs",
        resource_id=job_definition.id,
        actor_user_id=current_user.id,
        description="Job definition created.",
        details={"code": job_definition.code, "schedule_type": job_definition.schedule_type.value},
        request_context=request.state.request_audit_context,
    )
    return response


@job_definitions_router.get("/{job_definition_id}", response_model=JobDefinitionResponse)
def get_job_definition_endpoint(
    job_definition_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("jobs.read")),
) -> JobDefinitionResponse:
    job_definition = get_job_definition(session, job_definition_id)
    return serialize_job_definition(job_definition)


@job_definitions_router.patch("/{job_definition_id}", response_model=JobDefinitionResponse)
def update_job_definition_endpoint(
    job_definition_id: uuid.UUID,
    payload: JobDefinitionUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("jobs.write")),
) -> JobDefinitionResponse:
    job_definition = update_job_definition(session, job_definition_id=job_definition_id, payload=payload)
    response = serialize_job_definition(job_definition)
    record_audit_event(
        session,
        action="jobs.definitions.update",
        resource_type="jobs",
        resource_id=job_definition.id,
        actor_user_id=current_user.id,
        description="Job definition updated.",
        details=payload.model_dump(exclude_unset=True),
        request_context=request.state.request_audit_context,
    )
    return response


@job_definitions_router.post("/{job_definition_id}/runs", response_model=JobRunResponse, status_code=status.HTTP_201_CREATED)
def create_manual_job_run_endpoint(
    job_definition_id: uuid.UUID,
    payload: ManualJobRunCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("jobs.write")),
) -> JobRunResponse:
    job_run = create_manual_job_run(session, job_definition_id=job_definition_id, payload=payload)
    response = serialize_job_run(job_run)
    record_audit_event(
        session,
        action="jobs.runs.create",
        resource_type="job_runs",
        resource_id=job_run.id,
        actor_user_id=current_user.id,
        description="Manual job run created.",
        details={"job_definition_id": str(job_definition_id), "target_meter_id": str(job_run.target_meter_id) if job_run.target_meter_id else None},
        request_context=request.state.request_audit_context,
    )
    return response


@job_definitions_router.post(
    "/{job_definition_id}/targets",
    response_model=JobDefinitionTargetAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_job_definition_target_endpoint(
    job_definition_id: uuid.UUID,
    payload: JobDefinitionTargetAssignmentCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("jobs.targets.write")),
) -> JobDefinitionTargetAssignmentResponse:
    assignment = assign_job_definition_target(session, job_definition_id=job_definition_id, payload=payload)
    response = serialize_job_definition_target(assignment)
    record_audit_event(
        session,
        action="jobs.targets.assign",
        resource_type="job_definition_target_assignments",
        resource_id=assignment.id,
        actor_user_id=current_user.id,
        description="Job definition target assigned.",
        details={"job_definition_id": str(job_definition_id), "target_meter_id": str(assignment.target_meter_id)},
        request_context=request.state.request_audit_context,
    )
    return response


@job_definitions_router.get(
    "/{job_definition_id}/targets",
    response_model=JobDefinitionTargetAssignmentListResponse,
)
def list_job_definition_targets_endpoint(
    job_definition_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("jobs.targets.read")),
) -> JobDefinitionTargetAssignmentListResponse:
    return list_job_definition_targets(session, job_definition_id=job_definition_id)


@job_runs_router.get("", response_model=JobRunListResponse)
def list_job_runs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("jobs.runs.read")),
) -> JobRunListResponse:
    return list_job_runs(session, limit=limit)


@job_runs_router.get("/{job_run_id}", response_model=JobRunResponse)
def get_job_run_endpoint(
    job_run_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("jobs.runs.read")),
) -> JobRunResponse:
    job_run = get_job_run(session, job_run_id)
    return serialize_job_run(job_run)


@command_control_router.post("/{command_id}/cancel", response_model=CommandCancelResponse)
def cancel_command_endpoint(
    command_id: uuid.UUID,
    payload: CommandCancelRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.cancel")),
) -> CommandCancelResponse:
    response = cancel_command(session, command_id=command_id, payload=payload)
    record_audit_event(
        session,
        action="commands.cancel",
        resource_type="commands",
        resource_id=command_id,
        actor_user_id=current_user.id,
        description="Command cancelled.",
        details={"previous_status": response.previous_status.value, "reason": payload.reason},
        request_context=request.state.request_audit_context,
    )
    return response


@internal_job_runs_router.post("/claim", response_model=WorkerClaimResponse, dependencies=[Depends(require_internal_api_token)])
def claim_job_runs_endpoint(
    payload: WorkerClaimRequest,
    session: Session = Depends(get_db_session),
) -> WorkerClaimResponse:
    return claim_job_runs(session, payload)


@internal_scheduler_router.post(
    "/generate-due-runs",
    response_model=GenerateDueRunsResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def generate_due_runs_endpoint(
    payload: GenerateDueRunsRequest,
    session: Session = Depends(get_db_session),
) -> GenerateDueRunsResponse:
    return generate_due_runs(session, payload)


@internal_job_runs_router.post(
    "/{job_run_id}/materialize-command",
    response_model=MaterializeCommandResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def materialize_job_run_command_endpoint(
    job_run_id: uuid.UUID,
    session: Session = Depends(get_db_session),
) -> MaterializeCommandResponse:
    return materialize_job_run_command(session, job_run_id=job_run_id)


@internal_job_runs_router.post(
    "/{job_run_id}/prepare-for-execution",
    response_model=PrepareJobRunForExecutionResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def prepare_job_run_for_execution_endpoint(
    job_run_id: uuid.UUID,
    payload: PrepareJobRunForExecutionRequest,
    session: Session = Depends(get_db_session),
) -> PrepareJobRunForExecutionResponse:
    return prepare_job_run_for_execution(session, job_run_id=job_run_id, payload=payload)


@internal_job_runs_router.post(
    "/{job_run_id}/renew-claim",
    response_model=JobRunResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def renew_job_run_claim_endpoint(
    job_run_id: uuid.UUID,
    payload: WorkerLeaseRenewRequest,
    session: Session = Depends(get_db_session),
) -> JobRunResponse:
    job_run = renew_job_run_claim(session, job_run_id=job_run_id, payload=payload)
    return serialize_job_run(job_run)


@internal_job_runs_router.post(
    "/{job_run_id}/complete",
    response_model=JobRunResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def complete_job_run_endpoint(
    job_run_id: uuid.UUID,
    payload: JobRunCompleteRequest,
    session: Session = Depends(get_db_session),
) -> JobRunResponse:
    job_run = complete_job_run(session, job_run_id=job_run_id, payload=payload)
    return serialize_job_run(job_run)


@internal_job_runs_router.post(
    "/{job_run_id}/fail",
    response_model=JobRunResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def fail_job_run_endpoint(
    job_run_id: uuid.UUID,
    payload: JobRunFailRequest,
    session: Session = Depends(get_db_session),
) -> JobRunResponse:
    job_run = fail_job_run(session, job_run_id=job_run_id, payload=payload)
    return serialize_job_run(job_run)


@internal_job_runs_router.post(
    "/{job_run_id}/start-command-attempt",
    response_model=CommandExecutionAttemptResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def start_command_attempt_endpoint(
    job_run_id: uuid.UUID,
    payload: StartCommandAttemptRequest,
    session: Session = Depends(get_db_session),
) -> CommandExecutionAttemptResponse:
    attempt = start_command_attempt(session, job_run_id=job_run_id, payload=payload)
    from app.modules.commands.service import serialize_command_attempt

    return serialize_command_attempt(attempt)


@internal_command_attempts_router.post(
    "/{attempt_id}/mark-running",
    response_model=CommandExecutionAttemptResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def mark_command_attempt_running_endpoint(
    attempt_id: uuid.UUID,
    payload: MarkCommandAttemptRunningRequest,
    session: Session = Depends(get_db_session),
) -> CommandExecutionAttemptResponse:
    attempt = mark_command_attempt_running(session, attempt_id=attempt_id, payload=payload)
    from app.modules.commands.service import serialize_command_attempt

    return serialize_command_attempt(attempt)


@internal_command_attempts_router.post(
    "/{attempt_id}/succeed",
    response_model=CommandExecutionAttemptResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def succeed_command_attempt_endpoint(
    attempt_id: uuid.UUID,
    payload: CommandAttemptSucceedRequest,
    session: Session = Depends(get_db_session),
) -> CommandExecutionAttemptResponse:
    attempt = succeed_command_attempt(session, attempt_id=attempt_id, payload=payload)
    from app.modules.commands.service import serialize_command_attempt

    return serialize_command_attempt(attempt)


@internal_command_attempts_router.post(
    "/{attempt_id}/fail",
    response_model=CommandExecutionAttemptResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def fail_command_attempt_endpoint(
    attempt_id: uuid.UUID,
    payload: CommandAttemptFailRequest,
    session: Session = Depends(get_db_session),
) -> CommandExecutionAttemptResponse:
    attempt = fail_command_attempt(session, attempt_id=attempt_id, payload=payload)
    from app.modules.commands.service import serialize_command_attempt

    return serialize_command_attempt(attempt)


@internal_command_attempts_router.post(
    "/{attempt_id}/timeout",
    response_model=CommandExecutionAttemptResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def timeout_command_attempt_endpoint(
    attempt_id: uuid.UUID,
    payload: CommandAttemptTimeoutRequest,
    session: Session = Depends(get_db_session),
) -> CommandExecutionAttemptResponse:
    attempt = timeout_command_attempt(session, attempt_id=attempt_id, payload=payload)
    from app.modules.commands.service import serialize_command_attempt

    return serialize_command_attempt(attempt)
