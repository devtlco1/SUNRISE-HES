from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from croniter import croniter
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.commands.enums import CommandExecutionAttemptStatus, CommandStatus
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.schemas import MeterCommandCreate
from app.modules.commands.service import (
    apply_command_status_transition,
    create_meter_command,
    get_meter_command,
    serialize_command_attempt,
    serialize_meter_command,
)
from app.modules.jobs.enums import JobRunStatus, JobScheduleType
from app.modules.jobs.models import JobDefinition, JobDefinitionTargetAssignment, JobRun
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
    PrepareForExecutionRequest,
    PrepareForExecutionResponse,
    JobRunCompleteRequest,
    JobRunFailRequest,
    JobRunListResponse,
    JobRunRelatedCommandSummary,
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
from app.modules.commands.schemas import CommandExecutionAttemptResponse
from app.modules.meters.models import Meter

CLAIMABLE_JOB_STATUSES = {JobRunStatus.PENDING}
MATERIALIZABLE_JOB_RUN_STATUSES = {
    JobRunStatus.PENDING,
    JobRunStatus.CLAIMED,
    JobRunStatus.RUNNING,
}
SCHEDULABLE_JOB_DEFINITION_TYPES = {
    JobScheduleType.ONCE,
    JobScheduleType.INTERVAL,
    JobScheduleType.CRON,
}
COMMAND_TRANSITIONS = {
    CommandStatus.PENDING: {
        CommandStatus.SCHEDULED,
        CommandStatus.QUEUED,
        CommandStatus.IN_PROGRESS,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    },
    CommandStatus.SCHEDULED: {
        CommandStatus.QUEUED,
        CommandStatus.IN_PROGRESS,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    },
    CommandStatus.QUEUED: {
        CommandStatus.IN_PROGRESS,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    },
    CommandStatus.IN_PROGRESS: {
        CommandStatus.RETRY_WAIT,
        CommandStatus.SUCCEEDED,
        CommandStatus.FAILED,
        CommandStatus.TIMED_OUT,
    },
    CommandStatus.RETRY_WAIT: {
        CommandStatus.QUEUED,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    },
}
CANCELLABLE_COMMAND_STATUSES = {
    CommandStatus.PENDING,
    CommandStatus.SCHEDULED,
    CommandStatus.QUEUED,
    CommandStatus.RETRY_WAIT,
}


def list_job_definitions(session: Session) -> JobDefinitionListResponse:
    total = session.scalar(select(func.count()).select_from(JobDefinition)) or 0
    items = session.scalars(select(JobDefinition).order_by(JobDefinition.name.asc())).all()
    return JobDefinitionListResponse(
        total=total,
        items=[serialize_job_definition(item) for item in items],
    )


def get_job_definition(session: Session, job_definition_id: uuid.UUID) -> JobDefinition:
    job_definition = session.scalar(
        select(JobDefinition)
        .options(selectinload(JobDefinition.targets))
        .where(JobDefinition.id == job_definition_id)
    )
    if job_definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job definition not found.")
    return job_definition


def create_job_definition(session: Session, payload: JobDefinitionCreate) -> JobDefinition:
    existing = session.scalar(
        select(JobDefinition).where(func.lower(JobDefinition.code) == payload.code.lower())
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job definition code already exists.")

    _validate_schedule_payload(
        payload.schedule_type,
        payload.run_at,
        payload.cron_expression,
        payload.interval_seconds,
    )

    job_definition = JobDefinition(**payload.model_dump())
    job_definition.code = job_definition.code.strip().lower()
    job_definition.name = job_definition.name.strip()
    session.add(job_definition)
    session.commit()
    session.refresh(job_definition)
    return job_definition


def update_job_definition(
    session: Session,
    *,
    job_definition_id: uuid.UUID,
    payload: JobDefinitionUpdate,
) -> JobDefinition:
    job_definition = get_job_definition(session, job_definition_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job_definition, field, value)
    _validate_schedule_payload(
        job_definition.schedule_type,
        job_definition.run_at,
        job_definition.cron_expression,
        job_definition.interval_seconds,
    )
    session.add(job_definition)
    session.commit()
    session.refresh(job_definition)
    return job_definition


def create_manual_job_run(
    session: Session,
    *,
    job_definition_id: uuid.UUID,
    payload: ManualJobRunCreate,
) -> JobRun:
    job_definition = get_job_definition(session, job_definition_id)
    scheduled_for = payload.scheduled_for or datetime.now(UTC)
    available_at = payload.available_at or scheduled_for

    if payload.target_meter_id is not None and session.get(Meter, payload.target_meter_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target meter not found.")

    job_run = JobRun(
        job_definition_id=job_definition_id,
        target_meter_id=payload.target_meter_id,
        target_endpoint_id=payload.target_endpoint_id,
        scheduled_for=scheduled_for,
        available_at=available_at,
        status=JobRunStatus.PENDING,
        correlation_id=payload.correlation_id,
        request_payload=payload.request_payload or job_definition.default_payload,
        max_retries=job_definition.max_retries,
        retry_count=0,
    )
    session.add(job_run)
    session.commit()
    session.refresh(job_run)
    return job_run


def assign_job_definition_target(
    session: Session,
    *,
    job_definition_id: uuid.UUID,
    payload: JobDefinitionTargetAssignmentCreate,
) -> JobDefinitionTargetAssignment:
    job_definition = get_job_definition(session, job_definition_id)
    if job_definition.target_type.value != "meter":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only meter-targeted job definitions support target assignments in this phase.",
        )
    meter = session.get(Meter, payload.target_meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target meter not found.")

    existing = session.scalar(
        select(JobDefinitionTargetAssignment).where(
            JobDefinitionTargetAssignment.job_definition_id == job_definition_id,
            JobDefinitionTargetAssignment.target_meter_id == payload.target_meter_id,
        )
    )
    if existing is not None:
        if existing.is_active:
            return existing
        existing.is_active = True
        existing.unassigned_at = None
        existing.notes = payload.notes
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    assignment = JobDefinitionTargetAssignment(
        job_definition_id=job_definition_id,
        target_meter_id=payload.target_meter_id,
        notes=payload.notes,
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return assignment


def list_job_definition_targets(
    session: Session,
    *,
    job_definition_id: uuid.UUID,
) -> JobDefinitionTargetAssignmentListResponse:
    total = session.scalar(
        select(func.count()).select_from(JobDefinitionTargetAssignment).where(
            JobDefinitionTargetAssignment.job_definition_id == job_definition_id
        )
    ) or 0
    items = session.scalars(
        select(JobDefinitionTargetAssignment)
        .where(JobDefinitionTargetAssignment.job_definition_id == job_definition_id)
        .order_by(JobDefinitionTargetAssignment.assigned_at.desc())
    ).all()
    return JobDefinitionTargetAssignmentListResponse(
        total=total,
        items=[serialize_job_definition_target(item) for item in items],
    )


def list_job_runs(session: Session, *, limit: int = 50) -> JobRunListResponse:
    total = session.scalar(select(func.count()).select_from(JobRun)) or 0
    items = session.scalars(select(JobRun).order_by(JobRun.scheduled_for.desc()).limit(limit)).all()
    return JobRunListResponse(total=total, items=[serialize_job_run(item) for item in items])


def get_job_run(session: Session, job_run_id: uuid.UUID) -> JobRun:
    job_run = session.scalar(
        select(JobRun)
        .options(selectinload(JobRun.related_command).selectinload(MeterCommand.command_template))
        .where(JobRun.id == job_run_id)
    )
    if job_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found.")
    return job_run


def claim_job_runs(session: Session, payload: WorkerClaimRequest) -> WorkerClaimResponse:
    now = datetime.now(UTC)
    claim_expires_at = now + timedelta(seconds=payload.lease_seconds)
    statement = (
        select(JobRun)
        .where(
            JobRun.status.in_(list(CLAIMABLE_JOB_STATUSES)),
            JobRun.available_at <= now,
            or_(JobRun.claim_expires_at.is_(None), JobRun.claim_expires_at <= now),
        )
        .order_by(JobRun.available_at.asc(), JobRun.scheduled_for.asc())
        .with_for_update(skip_locked=True)
        .limit(payload.limit)
    )
    job_runs = session.scalars(statement).all()
    for job_run in job_runs:
        job_run.claimed_at = now
        job_run.claim_expires_at = claim_expires_at
        job_run.worker_identifier = payload.worker_identifier
        job_run.status = JobRunStatus.CLAIMED
        session.add(job_run)
    session.commit()
    return WorkerClaimResponse(
        claimed_count=len(job_runs),
        items=[serialize_job_run(job_run) for job_run in job_runs],
    )


def renew_job_run_claim(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    payload: WorkerLeaseRenewRequest,
) -> JobRun:
    job_run = get_job_run(session, job_run_id)
    if job_run.worker_identifier != payload.worker_identifier:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is claimed by another worker.")
    if job_run.status not in {JobRunStatus.CLAIMED, JobRunStatus.RUNNING}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is not claim-renewable.")
    job_run.claim_expires_at = datetime.now(UTC) + timedelta(seconds=payload.lease_seconds)
    session.add(job_run)
    session.commit()
    session.refresh(job_run)
    return job_run


def complete_job_run(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    payload: JobRunCompleteRequest,
) -> JobRun:
    job_run = get_job_run(session, job_run_id)
    _ensure_worker_owns_job_run(job_run, payload.worker_identifier)
    if job_run.status not in {JobRunStatus.CLAIMED, JobRunStatus.RUNNING}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is not completable.")
    job_run.status = JobRunStatus.SUCCEEDED
    job_run.started_at = job_run.started_at or datetime.now(UTC)
    job_run.completed_at = datetime.now(UTC)
    job_run.claim_expires_at = None
    job_run.result_summary = payload.result_summary
    job_run.related_command_id = payload.related_command_id or job_run.related_command_id
    session.add(job_run)
    session.commit()
    session.refresh(job_run)
    return job_run


def fail_job_run(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    payload: JobRunFailRequest,
) -> JobRun:
    job_run = get_job_run(session, job_run_id)
    _ensure_worker_owns_job_run(job_run, payload.worker_identifier)
    if job_run.status not in {JobRunStatus.CLAIMED, JobRunStatus.RUNNING}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is not fail-able.")
    job_run.retry_count += 1
    job_run.started_at = job_run.started_at or datetime.now(UTC)
    job_run.completed_at = datetime.now(UTC)
    job_run.latest_error_code = payload.latest_error_code
    job_run.latest_error_message = payload.latest_error_message
    job_run.result_summary = payload.result_summary
    job_run.claim_expires_at = None
    job_run.status = (
        JobRunStatus.PENDING if job_run.retry_count <= job_run.max_retries else JobRunStatus.FAILED
    )
    if job_run.status == JobRunStatus.PENDING:
        job_run.available_at = datetime.now(UTC)
        job_run.worker_identifier = None
        job_run.claimed_at = None
    session.add(job_run)
    session.commit()
    session.refresh(job_run)
    return job_run


def transition_command_status(
    session: Session,
    *,
    command_id: uuid.UUID,
    new_status: CommandStatus,
    latest_error_message: str | None = None,
) -> MeterCommand:
    command = get_meter_command(session, command_id)
    apply_command_status_transition(
        command,
        new_status=new_status,
        latest_error_message=latest_error_message,
        now=datetime.now(UTC),
    )
    session.add(command)
    session.commit()
    return get_meter_command(session, command.id)


def cancel_command(
    session: Session,
    *,
    command_id: uuid.UUID,
    payload: CommandCancelRequest,
) -> CommandCancelResponse:
    command = get_meter_command(session, command_id)
    previous_status = command.current_status
    if previous_status not in CANCELLABLE_COMMAND_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Command cannot be cancelled from status {previous_status.value}.",
        )
    updated = transition_command_status(
        session,
        command_id=command_id,
        new_status=CommandStatus.CANCELLED,
        latest_error_message=payload.reason,
    )
    return CommandCancelResponse(
        command_id=updated.id,
        previous_status=previous_status,
        current_status=updated.current_status,
        latest_error_message=updated.latest_error_message,
    )


def materialize_job_run_command(
    session: Session,
    *,
    job_run_id: uuid.UUID,
) -> MaterializeCommandResponse:
    job_run = session.scalar(
        select(JobRun)
        .options(
            selectinload(JobRun.job_definition),
            selectinload(JobRun.related_command).selectinload(MeterCommand.command_template),
        )
        .where(JobRun.id == job_run_id)
        .with_for_update()
    )
    if job_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found.")

    if job_run.status not in MATERIALIZABLE_JOB_RUN_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job run cannot be materialized from status {job_run.status.value}.",
        )

    command, materialized = _materialize_job_run_command_locked(session, job_run)
    session.commit()
    refreshed_job_run = get_job_run(session, job_run.id)
    return MaterializeCommandResponse(
        materialized=materialized,
        job_run=serialize_job_run(refreshed_job_run),
        command=serialize_meter_command(command),
    )


def generate_due_runs(session: Session, payload: GenerateDueRunsRequest) -> GenerateDueRunsResponse:
    as_of = payload.as_of or datetime.now(UTC)
    window_end = as_of + timedelta(seconds=payload.window_seconds)
    statement = (
        select(JobDefinition)
        .options(selectinload(JobDefinition.targets))
        .where(JobDefinition.is_active.is_(True))
    )
    if payload.job_definition_id is not None:
        statement = statement.where(JobDefinition.id == payload.job_definition_id)
    job_definitions = session.scalars(statement.order_by(JobDefinition.code.asc())).all()

    created_runs: list[JobRun] = []
    skipped_existing_count = 0

    for job_definition in job_definitions:
        targets = _resolve_generation_targets(job_definition)
        if not targets:
            continue
        occurrences = _compute_due_occurrences(
            job_definition=job_definition,
            as_of=as_of,
            window_end=window_end,
            limit=payload.limit_per_definition,
        )
        for scheduled_for in occurrences:
            for target_meter_id in targets:
                existing = _find_existing_job_run(
                    session,
                    job_definition_id=job_definition.id,
                    target_meter_id=target_meter_id,
                    scheduled_for=scheduled_for,
                )
                if existing is not None:
                    skipped_existing_count += 1
                    continue

                job_run = JobRun(
                    job_definition_id=job_definition.id,
                    target_meter_id=target_meter_id,
                    scheduled_for=scheduled_for,
                    available_at=scheduled_for,
                    status=JobRunStatus.PENDING,
                    request_payload=job_definition.default_payload,
                    max_retries=job_definition.max_retries,
                    retry_count=0,
                )
                session.add(job_run)
                try:
                    session.flush()
                except IntegrityError:
                    session.rollback()
                    skipped_existing_count += 1
                    continue
                created_runs.append(job_run)

    session.commit()
    refreshed_runs = [get_job_run(session, job_run.id) for job_run in created_runs]
    return GenerateDueRunsResponse(
        created_count=len(refreshed_runs),
        skipped_existing_count=skipped_existing_count,
        items=[serialize_job_run(job_run) for job_run in refreshed_runs],
    )


def serialize_job_definition(item: JobDefinition) -> JobDefinitionResponse:
    return JobDefinitionResponse(
        id=item.id,
        code=item.code,
        name=item.name,
        category=item.category,
        target_type=item.target_type,
        schedule_type=item.schedule_type,
        run_at=item.run_at,
        cron_expression=item.cron_expression,
        interval_seconds=item.interval_seconds,
        command_template_id=item.command_template_id,
        default_payload=item.default_payload,
        priority=item.priority,
        timeout_seconds=item.timeout_seconds,
        max_retries=item.max_retries,
        is_active=item.is_active,
        notes=item.notes,
    )


def serialize_job_run(item: JobRun) -> JobRunResponse:
    return JobRunResponse(
        id=item.id,
        job_definition_id=item.job_definition_id,
        target_meter_id=item.target_meter_id,
        target_endpoint_id=item.target_endpoint_id,
        related_command_id=item.related_command_id,
        scheduled_for=item.scheduled_for,
        available_at=item.available_at,
        claimed_at=item.claimed_at,
        claim_expires_at=item.claim_expires_at,
        worker_identifier=item.worker_identifier,
        status=item.status,
        started_at=item.started_at,
        completed_at=item.completed_at,
        cancelled_at=item.cancelled_at,
        retry_count=item.retry_count,
        max_retries=item.max_retries,
        request_payload=item.request_payload,
        result_summary=item.result_summary,
        latest_error_code=item.latest_error_code,
        latest_error_message=item.latest_error_message,
        correlation_id=item.correlation_id,
        related_command=(
            JobRunRelatedCommandSummary(
                id=item.related_command.id,
                current_status=item.related_command.current_status,
                command_template_id=item.related_command.command_template_id,
                command_template_code=item.related_command.command_template.code,
            )
            if item.related_command is not None
            else None
        ),
    )


def _validate_schedule_payload(
    schedule_type: JobScheduleType,
    run_at: datetime | None,
    cron_expression: str | None,
    interval_seconds: int | None,
) -> None:
    if schedule_type == JobScheduleType.ONCE and run_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_at is required for once schedules.")
    if schedule_type == JobScheduleType.CRON and not cron_expression:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cron_expression is required for cron schedules.")
    if schedule_type == JobScheduleType.INTERVAL and not interval_seconds:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval_seconds is required for interval schedules.")


def _ensure_worker_owns_job_run(job_run: JobRun, worker_identifier: str) -> None:
    if job_run.worker_identifier != worker_identifier:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is claimed by another worker.")


def prepare_job_run_for_execution(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    payload: PrepareForExecutionRequest,
) -> PrepareForExecutionResponse:
    claimed = _claim_specific_job_run(
        session,
        job_run_id=job_run_id,
        worker_identifier=payload.worker_identifier,
        lease_seconds=payload.lease_seconds,
    )
    materialized = materialize_job_run_command(session, job_run_id=job_run_id)
    command = get_meter_command(session, materialized.command.id)
    attempt, started = _get_or_start_attempt_for_prepared_job_run(
        session,
        job_run_id=job_run_id,
        command_id=command.id,
        worker_identifier=payload.worker_identifier,
    )
    refreshed_job_run = get_job_run(session, job_run_id)
    return PrepareForExecutionResponse(
        job_run_claimed=claimed,
        command_materialized=materialized.materialized,
        attempt_started=started,
        job_run=serialize_job_run(refreshed_job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _resolve_generation_targets(job_definition: JobDefinition) -> list[uuid.UUID | None]:
    if job_definition.schedule_type not in SCHEDULABLE_JOB_DEFINITION_TYPES:
        return []
    if job_definition.target_type.value == "meter":
        return [target.target_meter_id for target in job_definition.targets if target.is_active]
    if job_definition.target_type.value == "system":
        return [None]
    return []


def _claim_specific_job_run(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    worker_identifier: str,
    lease_seconds: int,
) -> bool:
    now = datetime.now(UTC)
    claim_expires_at = now + timedelta(seconds=lease_seconds)
    job_run = session.scalar(
        select(JobRun)
        .where(JobRun.id == job_run_id)
        .with_for_update()
    )
    if job_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found.")

    if job_run.status == JobRunStatus.PENDING:
        if job_run.available_at > now:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is not yet due for execution.")
        job_run.claimed_at = now
        job_run.claim_expires_at = claim_expires_at
        job_run.worker_identifier = worker_identifier
        job_run.status = JobRunStatus.CLAIMED
        session.add(job_run)
        session.commit()
        return True

    if job_run.status == JobRunStatus.CLAIMED:
        if job_run.worker_identifier == worker_identifier:
            return False
        if job_run.claim_expires_at is not None and job_run.claim_expires_at <= now:
            job_run.claimed_at = now
            job_run.claim_expires_at = claim_expires_at
            job_run.worker_identifier = worker_identifier
            session.add(job_run)
            session.commit()
            return True
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is already claimed by another worker.")

    if job_run.status == JobRunStatus.RUNNING:
        if job_run.worker_identifier != worker_identifier:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is already running on another worker.")
        return False

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Job run cannot be prepared from status {job_run.status.value}.",
    )


def _compute_due_occurrences(
    *,
    job_definition: JobDefinition,
    as_of: datetime,
    window_end: datetime,
    limit: int,
) -> list[datetime]:
    if job_definition.schedule_type == JobScheduleType.MANUAL:
        return []

    if job_definition.schedule_type == JobScheduleType.ONCE:
        if job_definition.run_at is None:
            return []
        return [job_definition.run_at] if as_of <= job_definition.run_at <= window_end else []

    if job_definition.schedule_type == JobScheduleType.INTERVAL:
        if job_definition.interval_seconds is None:
            return []
        occurrences: list[datetime] = []
        origin = job_definition.run_at or job_definition.created_at
        current = origin
        while current <= window_end and len(occurrences) < limit:
            if current >= as_of:
                occurrences.append(current)
            current = current + timedelta(seconds=job_definition.interval_seconds)
        return occurrences

    if job_definition.schedule_type == JobScheduleType.CRON:
        if not job_definition.cron_expression:
            return []
        iterator = croniter(job_definition.cron_expression, as_of - timedelta(seconds=1))
        occurrences: list[datetime] = []
        while len(occurrences) < limit:
            next_occurrence = iterator.get_next(datetime)
            if next_occurrence > window_end:
                break
            occurrences.append(next_occurrence)
        return occurrences

    return []


def _find_existing_job_run(
    session: Session,
    *,
    job_definition_id: uuid.UUID,
    target_meter_id: uuid.UUID | None,
    scheduled_for: datetime,
) -> JobRun | None:
    statement = select(JobRun).where(
        JobRun.job_definition_id == job_definition_id,
        JobRun.scheduled_for == scheduled_for,
    )
    if target_meter_id is None:
        statement = statement.where(
            JobRun.target_meter_id.is_(None),
            JobRun.target_endpoint_id.is_(None),
        )
    else:
        statement = statement.where(JobRun.target_meter_id == target_meter_id)
    return session.scalar(statement)


def _get_or_start_attempt_for_prepared_job_run(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    command_id: uuid.UUID,
    worker_identifier: str,
) -> tuple[CommandExecutionAttempt, bool]:
    active_attempt = session.scalar(
        select(CommandExecutionAttempt).where(
            CommandExecutionAttempt.meter_command_id == command_id,
            CommandExecutionAttempt.ended_at.is_(None),
            CommandExecutionAttempt.status.in_(
                [CommandExecutionAttemptStatus.STARTED, CommandExecutionAttemptStatus.RUNNING]
            ),
        )
    )
    if active_attempt is not None:
        if active_attempt.worker_identifier != worker_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Command already has an active execution attempt owned by another worker.",
            )
        return active_attempt, False

    attempt = start_command_attempt(
        session,
        job_run_id=job_run_id,
        payload=StartCommandAttemptRequest(
            worker_identifier=worker_identifier,
            meter_command_id=command_id,
        ),
    )
    return attempt, True


def _materialize_job_run_command_locked(
    session: Session,
    job_run: JobRun,
) -> tuple[MeterCommand, bool]:
    if job_run.related_command is not None:
        return job_run.related_command, False

    job_definition = job_run.job_definition
    if job_definition.command_template_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job definition does not define a command template.",
        )
    if job_run.target_meter_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job run does not target a meter and cannot materialize a meter command.",
        )

    materialization_idempotency_key = f"job-run:{job_run.id}"
    existing_command = session.scalar(
        select(MeterCommand)
        .options(selectinload(MeterCommand.command_template))
        .where(MeterCommand.idempotency_key == materialization_idempotency_key)
    )
    if existing_command is not None:
        job_run.related_command_id = existing_command.id
        session.add(job_run)
        return existing_command, False

    merged_payload = _merge_payloads(job_definition.default_payload, job_run.request_payload)
    scheduled_at = job_run.scheduled_for if job_run.scheduled_for > datetime.now(UTC) else None
    command = create_meter_command(
        session,
        meter_id=job_run.target_meter_id,
        payload=MeterCommandCreate(
            command_template_id=job_definition.command_template_id,
            priority=job_definition.priority,
            scheduled_at=scheduled_at,
            correlation_id=job_run.correlation_id,
            idempotency_key=materialization_idempotency_key,
            request_payload=merged_payload,
            normalized_payload=merged_payload,
            notes=f"Materialized from job run {job_run.id}.",
        ),
        requested_by_user_id=None,
        commit=False,
    )
    job_run.related_command_id = command.id
    session.add(job_run)
    return command, True


def serialize_job_definition_target(
    item: JobDefinitionTargetAssignment,
) -> JobDefinitionTargetAssignmentResponse:
    return JobDefinitionTargetAssignmentResponse(
        id=item.id,
        job_definition_id=item.job_definition_id,
        target_meter_id=item.target_meter_id,
        assigned_at=item.assigned_at,
        unassigned_at=item.unassigned_at,
        is_active=item.is_active,
        notes=item.notes,
    )


def _merge_payloads(
    default_payload: dict[str, object] | None,
    override_payload: dict[str, object] | None,
) -> dict[str, object] | None:
    if default_payload is None and override_payload is None:
        return None
    if isinstance(default_payload, dict) and isinstance(override_payload, dict):
        return {**default_payload, **override_payload}
    return override_payload or default_payload


def start_command_attempt(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    payload: StartCommandAttemptRequest,
) -> CommandExecutionAttempt:
    job_run = get_job_run(session, job_run_id)
    _ensure_worker_owns_job_run(job_run, payload.worker_identifier)
    if job_run.status != JobRunStatus.CLAIMED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run must be claimed before starting an attempt.")

    command = get_meter_command(session, payload.meter_command_id)
    if job_run.related_command_id is not None and job_run.related_command_id != command.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job run is already linked to a different command.")

    active_attempt = session.scalar(
        select(CommandExecutionAttempt).where(
            CommandExecutionAttempt.meter_command_id == command.id,
            CommandExecutionAttempt.ended_at.is_(None),
            CommandExecutionAttempt.status.in_(
                [CommandExecutionAttemptStatus.STARTED, CommandExecutionAttemptStatus.RUNNING]
            ),
        )
    )
    if active_attempt is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Command already has an active execution attempt.")

    next_attempt_number = (session.scalar(
        select(func.max(CommandExecutionAttempt.attempt_number)).where(
            CommandExecutionAttempt.meter_command_id == command.id
        )
    ) or 0) + 1

    now = datetime.now(UTC)
    apply_command_status_transition(command, new_status=CommandStatus.IN_PROGRESS, now=now)
    job_run.status = JobRunStatus.RUNNING
    job_run.started_at = now
    job_run.related_command_id = command.id
    session.add(job_run)
    session.add(command)

    attempt = CommandExecutionAttempt(
        meter_command_id=command.id,
        job_run_id=job_run.id,
        attempt_number=next_attempt_number,
        status=CommandExecutionAttemptStatus.STARTED,
        started_at=now,
        worker_identifier=payload.worker_identifier,
        endpoint_id=payload.endpoint_id,
        session_history_id=payload.session_history_id,
        request_snapshot=payload.request_snapshot or command.normalized_payload or command.request_payload,
        execution_metadata=payload.execution_metadata,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def prepare_job_run_for_execution(
    session: Session,
    *,
    job_run_id: uuid.UUID,
    payload: PrepareJobRunForExecutionRequest,
) -> PrepareJobRunForExecutionResponse:
    now = datetime.now(UTC)
    job_run = session.scalar(
        select(JobRun)
        .options(
            selectinload(JobRun.job_definition),
            selectinload(JobRun.related_command).selectinload(MeterCommand.command_template),
        )
        .where(JobRun.id == job_run_id)
        .with_for_update()
    )
    if job_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found.")

    if job_run.status in {
        JobRunStatus.SUCCEEDED,
        JobRunStatus.FAILED,
        JobRunStatus.CANCELLED,
        JobRunStatus.TIMED_OUT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job run cannot be prepared from status {job_run.status.value}.",
        )

    job_run_claimed = False
    if job_run.status == JobRunStatus.PENDING:
        job_run.claimed_at = now
        job_run.claim_expires_at = now + timedelta(seconds=payload.lease_seconds)
        job_run.worker_identifier = payload.worker_identifier
        job_run.status = JobRunStatus.CLAIMED
        job_run_claimed = True
    else:
        _ensure_worker_owns_job_run(job_run, payload.worker_identifier)

    command, command_materialized = _materialize_job_run_command_locked(session, job_run)

    active_attempt = session.scalar(
        select(CommandExecutionAttempt)
        .where(
            CommandExecutionAttempt.meter_command_id == command.id,
            CommandExecutionAttempt.ended_at.is_(None),
            CommandExecutionAttempt.status.in_(
                [CommandExecutionAttemptStatus.STARTED, CommandExecutionAttemptStatus.RUNNING]
            ),
        )
        .with_for_update()
    )

    attempt_started = False
    if active_attempt is not None:
        if active_attempt.worker_identifier != payload.worker_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Command already has an active execution attempt owned by another worker.",
            )
        attempt = active_attempt
    else:
        if job_run.status not in {JobRunStatus.CLAIMED, JobRunStatus.RUNNING}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job run cannot start an attempt from status {job_run.status.value}.",
            )
        next_attempt_number = (
            session.scalar(
                select(func.max(CommandExecutionAttempt.attempt_number)).where(
                    CommandExecutionAttempt.meter_command_id == command.id
                )
            )
            or 0
        ) + 1
        apply_command_status_transition(command, new_status=CommandStatus.IN_PROGRESS, now=now)
        job_run.status = JobRunStatus.RUNNING
        job_run.started_at = job_run.started_at or now
        job_run.related_command_id = command.id
        attempt = CommandExecutionAttempt(
            meter_command_id=command.id,
            job_run_id=job_run.id,
            attempt_number=next_attempt_number,
            status=CommandExecutionAttemptStatus.STARTED,
            started_at=now,
            worker_identifier=payload.worker_identifier,
            endpoint_id=payload.endpoint_id,
            session_history_id=payload.session_history_id,
            request_snapshot=payload.request_snapshot or command.normalized_payload or command.request_payload,
            execution_metadata=payload.execution_metadata,
        )
        session.add(attempt)
        attempt_started = True

    session.add(job_run)
    session.add(command)
    session.commit()

    refreshed_job_run = get_job_run(session, job_run.id)
    refreshed_command = get_meter_command(session, command.id)
    refreshed_attempt = session.get(CommandExecutionAttempt, attempt.id)

    return PrepareJobRunForExecutionResponse(
        job_run=serialize_job_run(refreshed_job_run),
        related_command=serialize_meter_command(refreshed_command),
        created_or_existing_attempt=serialize_command_attempt(refreshed_attempt),
        job_run_claimed=job_run_claimed,
        command_materialized=command_materialized,
        attempt_started=attempt_started,
    )


def mark_command_attempt_running(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: MarkCommandAttemptRunningRequest,
) -> CommandExecutionAttempt:
    attempt = _get_active_attempt(session, attempt_id)
    _ensure_worker_owns_attempt(attempt, payload.worker_identifier)
    if attempt.status != CommandExecutionAttemptStatus.STARTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt is not in a startable state.")
    attempt.status = CommandExecutionAttemptStatus.RUNNING
    if payload.execution_metadata:
        attempt.execution_metadata = payload.execution_metadata
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def succeed_command_attempt(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: CommandAttemptSucceedRequest,
) -> CommandExecutionAttempt:
    attempt = _get_active_attempt(session, attempt_id)
    _ensure_worker_owns_attempt(attempt, payload.worker_identifier)
    command = get_meter_command(session, attempt.meter_command_id)
    job_run = _get_attempt_job_run(session, attempt)
    now = datetime.now(UTC)

    attempt.status = CommandExecutionAttemptStatus.SUCCEEDED
    attempt.ended_at = now
    attempt.response_snapshot = payload.response_snapshot
    attempt.bytes_sent = payload.bytes_sent
    attempt.bytes_received = payload.bytes_received
    attempt.latency_ms = payload.latency_ms
    attempt.session_history_id = payload.session_history_id or attempt.session_history_id

    apply_command_status_transition(command, new_status=CommandStatus.SUCCEEDED, now=now)
    command.result_summary = payload.result_summary
    job_run.status = JobRunStatus.SUCCEEDED
    job_run.completed_at = now
    job_run.claim_expires_at = None
    job_run.result_summary = payload.result_summary
    job_run.related_command_id = command.id

    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    return attempt


def fail_command_attempt(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: CommandAttemptFailRequest,
    timed_out: bool = False,
) -> CommandExecutionAttempt:
    attempt = _get_active_attempt(session, attempt_id)
    _ensure_worker_owns_attempt(attempt, payload.worker_identifier)
    command = get_meter_command(session, attempt.meter_command_id)
    job_run = _get_attempt_job_run(session, attempt)
    now = datetime.now(UTC)
    retry_delay_seconds = payload.retry_delay_seconds or 0

    attempt.status = CommandExecutionAttemptStatus.TIMED_OUT if timed_out else CommandExecutionAttemptStatus.FAILED
    attempt.ended_at = now
    attempt.error_code = payload.error_code if hasattr(payload, "error_code") else "TIMEOUT"
    attempt.error_message = payload.error_message or ("Execution timed out." if timed_out else None)
    attempt.response_snapshot = getattr(payload, "response_snapshot", None)
    attempt.execution_metadata = payload.execution_metadata
    attempt.bytes_sent = getattr(payload, "bytes_sent", None)
    attempt.bytes_received = getattr(payload, "bytes_received", None)
    attempt.latency_ms = getattr(payload, "latency_ms", None)
    attempt.session_history_id = payload.session_history_id or attempt.session_history_id

    retryable = command.retry_count < command.max_retries
    command.retry_count += 1
    if retryable:
        apply_command_status_transition(
            command,
            new_status=CommandStatus.RETRY_WAIT,
            latest_error_message=attempt.error_message,
            latest_error_code=attempt.error_code,
            now=now,
        )
        job_run.status = JobRunStatus.PENDING
        job_run.available_at = now + timedelta(seconds=retry_delay_seconds)
        job_run.claimed_at = None
        job_run.claim_expires_at = None
        job_run.worker_identifier = None
        job_run.completed_at = None
        job_run.retry_count += 1
        job_run.latest_error_code = attempt.error_code
        job_run.latest_error_message = attempt.error_message
    else:
        final_status = CommandStatus.TIMED_OUT if timed_out else CommandStatus.FAILED
        apply_command_status_transition(
            command,
            new_status=final_status,
            latest_error_message=attempt.error_message,
            latest_error_code=attempt.error_code,
            now=now,
        )
        job_run.status = JobRunStatus.TIMED_OUT if timed_out else JobRunStatus.FAILED
        job_run.completed_at = now
        job_run.claim_expires_at = None
        job_run.latest_error_code = attempt.error_code
        job_run.latest_error_message = attempt.error_message
        job_run.retry_count += 1

    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    return attempt


def timeout_command_attempt(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    payload: CommandAttemptTimeoutRequest,
) -> CommandExecutionAttempt:
    fail_payload = CommandAttemptFailRequest(
        worker_identifier=payload.worker_identifier,
        error_code="TIMEOUT",
        error_message=payload.error_message or "Execution timed out.",
        response_snapshot=None,
        execution_metadata=payload.execution_metadata,
        bytes_sent=None,
        bytes_received=None,
        latency_ms=None,
        session_history_id=payload.session_history_id,
        retry_delay_seconds=payload.retry_delay_seconds,
    )
    return fail_command_attempt(session, attempt_id=attempt_id, payload=fail_payload, timed_out=True)


def _get_active_attempt(session: Session, attempt_id: uuid.UUID) -> CommandExecutionAttempt:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command execution attempt not found.")
    if attempt.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Command execution attempt is already finalized.")
    return attempt


def _ensure_worker_owns_attempt(attempt: CommandExecutionAttempt, worker_identifier: str) -> None:
    if attempt.worker_identifier != worker_identifier:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt is owned by another worker.")


def _get_attempt_job_run(session: Session, attempt: CommandExecutionAttempt) -> JobRun:
    if attempt.job_run_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt is not linked to a job run.")
    return get_job_run(session, attempt.job_run_id)
