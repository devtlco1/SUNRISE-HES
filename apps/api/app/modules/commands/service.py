from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.commands.models import CommandExecutionAttempt, CommandTemplate, MeterCommand
from app.modules.commands.enums import (
    CommandCategory,
    CommandExecutionAttemptStatus,
    CommandStatus,
    RelayControlCommandOperation,
)
from app.modules.commands.schemas import (
    CaptureLoadProfileCommandCreate,
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
    ProfileCaptureAttemptBootstrapRequest,
    ProfileCaptureAttemptBootstrapResponse,
    ProfileCaptureAttemptBootstrapResult,
    RelayControlCommandCreate,
)
from app.modules.connectivity.enums import EndpointAssignmentStatus, ProtocolFamily
from app.modules.connectivity.models import MeterEndpointAssignment, ProtocolAssociationProfile
from app.modules.meters.models import Meter
from app.modules.readings.models import LoadProfileChannel


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


def submit_capture_load_profile_command(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: CaptureLoadProfileCommandCreate,
    requested_by_user_id: uuid.UUID | None,
) -> MeterCommand:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    template = get_command_template(session, payload.command_template_id)
    if template.category != CommandCategory.PROFILE_CAPTURE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected template is not compatible with the capture-load-profile command submission slice.",
        )
    if not template.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot request a command from an inactive template.",
        )

    if payload.interval_end <= payload.interval_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Capture-load-profile interval_end must be after interval_start.",
        )

    if payload.idempotency_key:
        existing = session.scalar(
            select(MeterCommand).where(MeterCommand.idempotency_key == payload.idempotency_key)
        )
        if existing is not None:
            if existing.meter_id != meter_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A command with that idempotency key already exists for another meter.",
                )
            existing = get_meter_command(session, existing.id)
            if existing.command_template.category != template.category.PROFILE_CAPTURE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A command with that idempotency key already exists for another command policy.",
                )
            return existing

    assignment = session.get(MeterEndpointAssignment, payload.endpoint_assignment_id)
    if assignment is None or assignment.meter_id != meter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Endpoint assignment is invalid for the selected meter.",
        )
    if assignment.assignment_status != EndpointAssignmentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Endpoint assignment is not active for the selected meter.",
        )

    profile = session.get(ProtocolAssociationProfile, payload.protocol_association_profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol association profile not found.",
        )
    if not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol association profile is not active.",
        )
    if profile.protocol_family != ProtocolFamily.DLMS_COSEM:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol association profile is not compatible with the capture-load-profile command submission slice.",
        )

    unique_channel_ids = list(dict.fromkeys(payload.channel_ids))
    channels = session.scalars(
        select(LoadProfileChannel).where(LoadProfileChannel.id.in_(unique_channel_ids))
    ).all()
    if len(channels) != len(unique_channel_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more load profile channels were not found.",
        )
    if any(channel.meter_id != meter_id for channel in channels):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Load profile channel is invalid for the selected meter.",
        )
    if any(not channel.is_active for channel in channels):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Load profile channel is not active for the selected meter.",
        )

    normalized_payload = _normalize_capture_load_profile_submission(
        payload,
        channels=channels,
    )
    command = create_meter_command(
        session,
        meter_id=meter_id,
        payload=MeterCommandCreate(
            command_template_id=payload.command_template_id,
            priority=payload.priority,
            scheduled_at=payload.scheduled_at,
            correlation_id=payload.correlation_id,
            idempotency_key=payload.idempotency_key,
            request_payload={
                "profile_read_operation": "capture_load_profile",
                "capture_load_profile": {
                    "channel_ids": [str(channel_id) for channel_id in unique_channel_ids],
                    "interval_start": payload.interval_start.isoformat(),
                    "interval_end": payload.interval_end.isoformat(),
                },
            },
            normalized_payload=normalized_payload,
            endpoint_assignment_id=payload.endpoint_assignment_id,
            protocol_association_profile_id=payload.protocol_association_profile_id,
            notes=payload.notes,
        ),
        requested_by_user_id=requested_by_user_id,
    )
    return command


RELAY_CONTROL_TARGET_INTERFACE_CLASS = "disconnect_control"
RELAY_CONTROL_TARGET_CLASS_ID = 70
RELAY_CONTROL_TARGET_OBIS_CODE = "0.0.96.3.10.255"


def submit_relay_control_command(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: RelayControlCommandCreate,
    requested_by_user_id: uuid.UUID | None,
) -> MeterCommand:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    template = get_command_template(session, payload.command_template_id)
    expected_category = _resolve_relay_control_category(payload.relay_operation)
    if template.category != expected_category:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected template is not compatible with the relay-control command submission slice.",
        )
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
            if existing.meter_id != meter_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A command with that idempotency key already exists for another meter.",
                )
            existing = get_meter_command(session, existing.id)
            if existing.command_template.category != expected_category:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A command with that idempotency key already exists for another command policy.",
                )
            return existing

    assignment = session.get(MeterEndpointAssignment, payload.endpoint_assignment_id)
    if assignment is None or assignment.meter_id != meter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Endpoint assignment is invalid for the selected meter.",
        )
    if assignment.assignment_status != EndpointAssignmentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Endpoint assignment is not active for the selected meter.",
        )

    profile = session.get(ProtocolAssociationProfile, payload.protocol_association_profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol association profile not found.",
        )
    if not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol association profile is not active.",
        )
    if profile.protocol_family != ProtocolFamily.DLMS_COSEM:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol association profile is not compatible with the relay-control command submission slice.",
        )

    _validate_relay_control_target(payload)
    normalized_payload = _normalize_relay_control_submission(payload)
    command = create_meter_command(
        session,
        meter_id=meter_id,
        payload=MeterCommandCreate(
            command_template_id=payload.command_template_id,
            priority=payload.priority,
            scheduled_at=payload.scheduled_at,
            correlation_id=payload.correlation_id,
            idempotency_key=payload.idempotency_key,
            request_payload={
                "relay_control_operation": payload.relay_operation.value,
                "relay_control": {
                    "target_interface_class": payload.relay_target_interface_class,
                    "target_obis_code": payload.relay_target_obis_code,
                },
            },
            normalized_payload=normalized_payload,
            endpoint_assignment_id=payload.endpoint_assignment_id,
            protocol_association_profile_id=payload.protocol_association_profile_id,
            notes=payload.notes,
        ),
        requested_by_user_id=requested_by_user_id,
    )
    return command


def _resolve_relay_control_category(
    operation: RelayControlCommandOperation,
) -> CommandCategory:
    if operation == RelayControlCommandOperation.DISCONNECT:
        return CommandCategory.REMOTE_DISCONNECT
    return CommandCategory.REMOTE_RECONNECT


def _validate_relay_control_target(payload: RelayControlCommandCreate) -> None:
    if payload.relay_target_interface_class != RELAY_CONTROL_TARGET_INTERFACE_CLASS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relay-control command target assumptions are not compatible with the bounded relay-control slice.",
        )
    if payload.relay_target_obis_code != RELAY_CONTROL_TARGET_OBIS_CODE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relay-control command target assumptions are not compatible with the bounded relay-control slice.",
        )


def _normalize_relay_control_submission(
    payload: RelayControlCommandCreate,
) -> dict[str, object]:
    expected_category = _resolve_relay_control_category(payload.relay_operation)
    return {
        "relay_control_operation": payload.relay_operation.value,
        "relay_control": {
            "operation": payload.relay_operation.value,
            "target_object": {
                "interface_class": payload.relay_target_interface_class,
                "class_id": RELAY_CONTROL_TARGET_CLASS_ID,
                "obis_code": payload.relay_target_obis_code,
                "method_name": (
                    "remote_disconnect"
                    if payload.relay_operation == RelayControlCommandOperation.DISCONNECT
                    else "remote_reconnect"
                ),
                "method_index": (
                    1 if payload.relay_operation == RelayControlCommandOperation.DISCONNECT else 2
                ),
            },
            "command_category": expected_category.value,
        },
    }


def _normalize_capture_load_profile_submission(
    payload: CaptureLoadProfileCommandCreate,
    *,
    channels: list[LoadProfileChannel],
) -> dict[str, object]:
    sorted_channels = sorted(channels, key=lambda item: item.channel_code)
    return {
        "profile_read_operation": "capture_load_profile",
        "capture_load_profile": {
            "interval_start": payload.interval_start.isoformat(),
            "interval_end": payload.interval_end.isoformat(),
            "channel_ids": [str(channel.id) for channel in sorted_channels],
            "channel_count": len(sorted_channels),
            "channels": [
                {
                    "channel_id": str(channel.id),
                    "channel_code": channel.channel_code,
                    "obis_code": channel.obis_code,
                    "interval_seconds": channel.interval_seconds,
                    "unit": channel.unit,
                }
                for channel in sorted_channels
            ],
        },
    }


def bootstrap_profile_capture_command_attempt(
    session: Session,
    *,
    command_id: uuid.UUID,
    payload: ProfileCaptureAttemptBootstrapRequest,
) -> ProfileCaptureAttemptBootstrapResponse:
    command = get_meter_command(session, command_id)
    template = command.command_template
    if template.category != CommandCategory.PROFILE_CAPTURE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the profile-capture bootstrap slice.",
        )
    if command.current_status in {
        CommandStatus.SUCCEEDED,
        CommandStatus.FAILED,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command is not bootstrap-eligible from its current state.",
        )

    normalized_payload = _validate_capture_load_profile_normalized_payload(command)
    assignment = _validate_profile_capture_endpoint_assignment(
        session,
        meter_id=command.meter_id,
        endpoint_assignment_id=command.endpoint_assignment_id,
    )
    profile = _validate_profile_capture_protocol_profile(
        session,
        protocol_association_profile_id=command.protocol_association_profile_id,
    )

    active_attempt = session.scalar(
        select(CommandExecutionAttempt)
        .where(
            CommandExecutionAttempt.meter_command_id == command.id,
            CommandExecutionAttempt.ended_at.is_(None),
            CommandExecutionAttempt.status.in_(
                [CommandExecutionAttemptStatus.STARTED, CommandExecutionAttemptStatus.RUNNING]
            ),
        )
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )
    if active_attempt is not None:
        existing_bootstrap = _load_profile_capture_attempt_bootstrap(
            active_attempt.execution_metadata
        )
        if existing_bootstrap is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile-capture command already has an incompatible active execution attempt.",
            )
        if existing_bootstrap.get("bootstrap_identifier") != payload.bootstrap_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile-capture command already has an active execution attempt owned by another bootstrap identifier.",
            )
        result = ProfileCaptureAttemptBootstrapResult(
            bootstrap_status="bootstrapped",
            command_id=command.id,
            command_execution_attempt_id=active_attempt.id,
            reused_existing_attempt=True,
            bootstrapped_at=datetime.fromisoformat(str(existing_bootstrap["bootstrapped_at"])),
            bootstrap_identifier=str(existing_bootstrap["bootstrap_identifier"]),
            correlation_id=command.correlation_id,
            endpoint_assignment_id=assignment.id,
            endpoint_id=assignment.endpoint_id,
            protocol_association_profile_id=profile.id,
            bootstrap_record=existing_bootstrap,
        )
        return ProfileCaptureAttemptBootstrapResponse(
            result=result,
            related_command=serialize_meter_command(command),
            created_or_existing_attempt=serialize_command_attempt(active_attempt),
        )

    previous_bootstrapped_attempt = session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command.id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )
    if previous_bootstrapped_attempt is not None:
        previous_bootstrap = _load_profile_capture_attempt_bootstrap(
            previous_bootstrapped_attempt.execution_metadata
        )
        if previous_bootstrap is not None and previous_bootstrapped_attempt.ended_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile-capture command already has a completed bootstrap attempt history.",
            )

    next_attempt_number = (
        session.scalar(
            select(func.max(CommandExecutionAttempt.attempt_number)).where(
                CommandExecutionAttempt.meter_command_id == command.id
            )
        )
        or 0
    ) + 1
    now = datetime.now(UTC)
    bootstrap_record = {
        "bootstrap_status": "bootstrapped",
        "command_id": str(command.id),
        "command_execution_attempt_id": None,
        "reused_existing_attempt": False,
        "bootstrapped_at": now.isoformat(),
        "bootstrap_identifier": payload.bootstrap_identifier,
        "bootstrap_reason": payload.bootstrap_reason,
        "correlation_id": command.correlation_id,
        "endpoint_assignment_id": str(assignment.id),
        "endpoint_id": str(assignment.endpoint_id),
        "protocol_association_profile_id": str(profile.id),
        "profile_read_operation": "capture_load_profile",
    }

    apply_command_status_transition(command, new_status=CommandStatus.IN_PROGRESS, now=now)
    attempt = CommandExecutionAttempt(
        meter_command_id=command.id,
        job_run_id=None,
        attempt_number=next_attempt_number,
        status=CommandExecutionAttemptStatus.STARTED,
        started_at=now,
        worker_identifier=payload.bootstrap_identifier,
        endpoint_id=assignment.endpoint_id,
        session_history_id=None,
        request_snapshot=normalized_payload,
        execution_metadata={"profile_capture_attempt_bootstrap": bootstrap_record},
    )
    session.add(command)
    session.add(attempt)
    session.flush()
    bootstrap_record["command_execution_attempt_id"] = str(attempt.id)
    attempt.execution_metadata = {"profile_capture_attempt_bootstrap": bootstrap_record}
    command.result_summary = {
        **(command.result_summary or {}),
        "profile_capture_attempt_bootstrap": bootstrap_record,
    }
    session.add(command)
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    refreshed_command = get_meter_command(session, command.id)

    result = ProfileCaptureAttemptBootstrapResult(
        bootstrap_status="bootstrapped",
        command_id=refreshed_command.id,
        command_execution_attempt_id=attempt.id,
        reused_existing_attempt=False,
        bootstrapped_at=now,
        bootstrap_identifier=payload.bootstrap_identifier,
        correlation_id=refreshed_command.correlation_id,
        endpoint_assignment_id=assignment.id,
        endpoint_id=assignment.endpoint_id,
        protocol_association_profile_id=profile.id,
        bootstrap_record=bootstrap_record,
    )
    return ProfileCaptureAttemptBootstrapResponse(
        result=result,
        related_command=serialize_meter_command(refreshed_command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _validate_capture_load_profile_normalized_payload(command: MeterCommand) -> dict[str, object]:
    normalized_payload = command.normalized_payload
    if not isinstance(normalized_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command is missing normalized payload for bootstrap.",
        )
    if normalized_payload.get("profile_read_operation") != "capture_load_profile":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command has incompatible normalized payload for bootstrap.",
        )
    capture_load_profile = normalized_payload.get("capture_load_profile")
    if not isinstance(capture_load_profile, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command has incompatible normalized payload for bootstrap.",
        )
    channel_ids = capture_load_profile.get("channel_ids")
    if not isinstance(channel_ids, list) or not channel_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command has incompatible normalized payload for bootstrap.",
        )
    return normalized_payload


def _validate_profile_capture_endpoint_assignment(
    session: Session,
    *,
    meter_id: uuid.UUID,
    endpoint_assignment_id: uuid.UUID | None,
) -> MeterEndpointAssignment:
    if endpoint_assignment_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command is missing endpoint continuity for bootstrap.",
        )
    assignment = session.get(MeterEndpointAssignment, endpoint_assignment_id)
    if assignment is None or assignment.meter_id != meter_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command has invalid endpoint continuity for bootstrap.",
        )
    if assignment.assignment_status != EndpointAssignmentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command has inactive endpoint continuity for bootstrap.",
        )
    return assignment


def _validate_profile_capture_protocol_profile(
    session: Session,
    *,
    protocol_association_profile_id: uuid.UUID | None,
) -> ProtocolAssociationProfile:
    if protocol_association_profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command is missing protocol continuity for bootstrap.",
        )
    profile = session.get(ProtocolAssociationProfile, protocol_association_profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command has invalid protocol continuity for bootstrap.",
        )
    if not profile.is_active or profile.protocol_family != ProtocolFamily.DLMS_COSEM:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command has incompatible protocol continuity for bootstrap.",
        )
    return profile


def _load_profile_capture_attempt_bootstrap(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("profile_capture_attempt_bootstrap")
    return payload if isinstance(payload, dict) else None


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
