from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.commands.models import CommandExecutionAttempt, CommandTemplate, MeterCommand
from app.modules.commands.schemas import (
    CommandExecutionAttemptListResponse,
    CommandExecutionAttemptResponse,
    CommandTemplateCreate,
    CommandTemplateListResponse,
    CommandTemplateResponse,
    CommandTemplateUpdate,
    MeterCommandCreate,
    MeterCommandDetailResponse,
    MeterCommandListResponse,
    MeterCommandResponse,
)
from app.modules.connectivity.models import MeterEndpointAssignment, ProtocolAssociationProfile
from app.modules.meters.models import Meter


def _command_options():
    return (
        selectinload(MeterCommand.command_template),
        selectinload(MeterCommand.attempts),
    )


def list_command_templates(session: Session) -> CommandTemplateListResponse:
    total = session.scalar(select(func.count()).select_from(CommandTemplate)) or 0
    items = session.scalars(select(CommandTemplate).order_by(CommandTemplate.name.asc())).all()
    return CommandTemplateListResponse(
        total=total,
        items=[serialize_command_template(item) for item in items],
    )


def get_command_template(session: Session, template_id: uuid.UUID) -> CommandTemplate:
    template = session.get(CommandTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command template not found.")
    return template


def create_command_template(session: Session, payload: CommandTemplateCreate) -> CommandTemplate:
    existing = session.scalar(
        select(CommandTemplate).where(func.lower(CommandTemplate.code) == payload.code.lower())
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Command template code already exists.")

    template = CommandTemplate(**payload.model_dump())
    template.code = template.code.strip().lower()
    template.name = template.name.strip()
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def update_command_template(
    session: Session,
    *,
    template_id: uuid.UUID,
    payload: CommandTemplateUpdate,
) -> CommandTemplate:
    template = get_command_template(session, template_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def create_meter_command(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: MeterCommandCreate,
    requested_by_user_id: uuid.UUID | None,
    commit: bool = True,
) -> MeterCommand:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    template = get_command_template(session, payload.command_template_id)
    if not template.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot request a command from an inactive template.",
        )

    if payload.idempotency_key:
        existing = session.scalar(
            select(MeterCommand).where(MeterCommand.idempotency_key == payload.idempotency_key)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A command with that idempotency key already exists.",
            )

    if payload.endpoint_assignment_id is not None:
        assignment = session.get(MeterEndpointAssignment, payload.endpoint_assignment_id)
        if assignment is None or assignment.meter_id != meter_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Endpoint assignment is invalid for the selected meter.",
            )

    if payload.protocol_association_profile_id is not None:
        profile = session.get(ProtocolAssociationProfile, payload.protocol_association_profile_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Protocol association profile not found.",
            )

    requested_at = datetime.now(UTC)
    scheduled_at = payload.scheduled_at
    timeout_reference = scheduled_at or requested_at
    timeout_at = timeout_reference + timedelta(seconds=template.timeout_seconds)

    command = MeterCommand(
        meter_id=meter_id,
        command_template_id=payload.command_template_id,
        requested_by_user_id=requested_by_user_id,
        endpoint_assignment_id=payload.endpoint_assignment_id,
        protocol_association_profile_id=payload.protocol_association_profile_id,
        correlation_id=payload.correlation_id,
        idempotency_key=payload.idempotency_key,
        priority=payload.priority,
        request_payload=payload.request_payload,
        normalized_payload=payload.normalized_payload or payload.request_payload,
        scheduled_at=scheduled_at,
        requested_at=requested_at,
        timeout_at=timeout_at,
        max_retries=template.max_retries,
        retry_count=0,
        notes=payload.notes,
    )
    session.add(command)
    if commit:
        session.commit()
        return get_meter_command(session, command.id)
    session.flush()
    return command


def list_meter_commands(
    session: Session,
    *,
    meter_id: uuid.UUID,
    limit: int = 50,
) -> MeterCommandListResponse:
    total = session.scalar(
        select(func.count()).select_from(MeterCommand).where(MeterCommand.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(MeterCommand)
        .options(*_command_options())
        .where(MeterCommand.meter_id == meter_id)
        .order_by(MeterCommand.requested_at.desc())
        .limit(limit)
    ).unique().all()
    return MeterCommandListResponse(total=total, items=[serialize_meter_command(item) for item in items])


def get_meter_command(session: Session, command_id: uuid.UUID) -> MeterCommand:
    command = session.scalar(
        select(MeterCommand)
        .options(*_command_options())
        .where(MeterCommand.id == command_id)
    )
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    return command


def list_command_attempts(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandExecutionAttemptListResponse:
    total = session.scalar(
        select(func.count()).select_from(CommandExecutionAttempt).where(
            CommandExecutionAttempt.meter_command_id == command_id
        )
    ) or 0
    items = session.scalars(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command_id)
        .order_by(CommandExecutionAttempt.attempt_number.asc())
    ).all()
    return CommandExecutionAttemptListResponse(
        total=total,
        items=[serialize_command_attempt(item) for item in items],
    )


def serialize_command_template(item: CommandTemplate) -> CommandTemplateResponse:
    return CommandTemplateResponse(
        id=item.id,
        code=item.code,
        name=item.name,
        category=item.category,
        description=item.description,
        target_scope=item.target_scope,
        payload_schema=item.payload_schema,
        timeout_seconds=item.timeout_seconds,
        max_retries=item.max_retries,
        is_active=item.is_active,
    )


def serialize_meter_command(item: MeterCommand) -> MeterCommandResponse:
    return MeterCommandResponse(
        id=item.id,
        meter_id=item.meter_id,
        command_template_id=item.command_template_id,
        command_template_code=item.command_template.code,
        command_template_name=item.command_template.name,
        current_status=item.current_status,
        priority=item.priority,
        requested_by_user_id=item.requested_by_user_id,
        requested_at=item.requested_at,
        scheduled_at=item.scheduled_at,
        queued_at=item.queued_at,
        started_at=item.started_at,
        completed_at=item.completed_at,
        timeout_at=item.timeout_at,
        correlation_id=item.correlation_id,
        idempotency_key=item.idempotency_key,
        request_payload=item.request_payload,
        normalized_payload=item.normalized_payload,
        result_summary=item.result_summary,
        latest_error_code=item.latest_error_code,
        latest_error_message=item.latest_error_message,
        max_retries=item.max_retries,
        retry_count=item.retry_count,
        endpoint_assignment_id=item.endpoint_assignment_id,
        protocol_association_profile_id=item.protocol_association_profile_id,
        notes=item.notes,
    )


def serialize_meter_command_detail(item: MeterCommand) -> MeterCommandDetailResponse:
    response = serialize_meter_command(item)
    return MeterCommandDetailResponse(
        **response.model_dump(),
        attempts=[serialize_command_attempt(attempt) for attempt in item.attempts],
    )


def serialize_command_attempt(item: CommandExecutionAttempt) -> CommandExecutionAttemptResponse:
    return CommandExecutionAttemptResponse(
        id=item.id,
        meter_command_id=item.meter_command_id,
        job_run_id=item.job_run_id,
        attempt_number=item.attempt_number,
        status=item.status,
        started_at=item.started_at,
        ended_at=item.ended_at,
        worker_identifier=item.worker_identifier,
        endpoint_id=item.endpoint_id,
        session_history_id=item.session_history_id,
        bytes_sent=item.bytes_sent,
        bytes_received=item.bytes_received,
        latency_ms=item.latency_ms,
        error_code=item.error_code,
        error_message=item.error_message,
        request_snapshot=item.request_snapshot,
        response_snapshot=item.response_snapshot,
        execution_metadata=item.execution_metadata,
    )


def apply_command_status_transition(
    command: MeterCommand,
    *,
    new_status,
    latest_error_message: str | None = None,
    latest_error_code: str | None = None,
    now: datetime | None = None,
) -> None:
    from app.modules.jobs.service import COMMAND_TRANSITIONS

    allowed = COMMAND_TRANSITIONS.get(command.current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid command status transition from {command.current_status.value} to {new_status.value}.",
        )

    effective_now = now or datetime.now(UTC)
    command.current_status = new_status
    if new_status.name == "QUEUED":
        command.queued_at = effective_now
        command.completed_at = None
    if new_status.name == "IN_PROGRESS":
        command.started_at = effective_now
        command.completed_at = None
    if new_status.name == "RETRY_WAIT":
        command.completed_at = None
    if new_status.name in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
        command.completed_at = effective_now
    if latest_error_message is not None:
        command.latest_error_message = latest_error_message
    if latest_error_code is not None:
        command.latest_error_code = latest_error_code
