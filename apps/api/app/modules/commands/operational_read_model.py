from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.commands.enums import (
    CommandApprovalStatus,
    CommandCategory,
    CommandOperationalFamily,
)
from app.modules.commands.models import CommandExecutionAttempt, CommandTemplate, MeterCommand
from app.modules.commands.profile_capture_status_readback import (
    get_profile_capture_execution_status,
)
from app.modules.commands.on_demand_read_status_readback import (
    get_on_demand_read_execution_status,
)
from app.modules.commands.relay_control_status_readback import (
    get_relay_control_execution_status,
)
from app.modules.commands.schemas import (
    CommandOperationalDetailResponse,
    CommandOperationalDetailResult,
    CommandOperationalRecentListItem,
    CommandOperationalRecentListResponse,
    MeterScopedCommandOperationalRecentListItem,
    MeterScopedCommandOperationalRecentListResponse,
)
from app.modules.commands.service import get_meter_command
from app.modules.meters.models import Meter


def get_command_operational_detail(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandOperationalDetailResponse:
    command = get_meter_command(session, command_id)
    latest_attempt = _load_latest_command_attempt(session, command_id=command.id)
    return CommandOperationalDetailResponse(
        result=_build_command_operational_detail_result(
            session,
            command=command,
            latest_attempt=latest_attempt,
            unsupported_detail="Selected command is not compatible with the commands operational detail read-model slice.",
        )
    )


def list_recent_command_operational_items(
    session: Session,
    *,
    limit: int = 20,
    family_filter: CommandOperationalFamily | None = None,
    approval_filter: CommandApprovalStatus | None = None,
) -> CommandOperationalRecentListResponse:
    projections = _list_command_operational_recent_items(
        session,
        limit=limit,
        family_filter=family_filter,
        approval_filter=approval_filter,
    )
    return CommandOperationalRecentListResponse(
        total=len(projections),
        limit=limit,
        family_filter=family_filter,
        approval_filter=approval_filter,
        items=projections,
    )


def list_recent_meter_command_operational_items(
    session: Session,
    *,
    meter_id: uuid.UUID,
    limit: int = 20,
    family_filter: CommandOperationalFamily | None = None,
) -> MeterScopedCommandOperationalRecentListResponse:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    items = _list_command_operational_recent_items(
        session,
        limit=limit,
        family_filter=family_filter,
        meter_id=meter_id,
    )
    return MeterScopedCommandOperationalRecentListResponse(
        meter_id=meter_id,
        total=len(items),
        limit=limit,
        family_filter=family_filter,
        items=[
            MeterScopedCommandOperationalRecentListItem(**item.model_dump())
            for item in items
        ],
    )


def _load_latest_command_attempt(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandExecutionAttempt | None:
    return session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command_id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )


def _list_command_operational_recent_items(
    session: Session,
    *,
    limit: int,
    family_filter: CommandOperationalFamily | None,
    approval_filter: CommandApprovalStatus | None = None,
    meter_id: uuid.UUID | None = None,
) -> list[CommandOperationalRecentListItem]:
    categories = _resolve_supported_categories(family_filter)
    query = (
        select(MeterCommand)
        .join(CommandTemplate, MeterCommand.command_template_id == CommandTemplate.id)
        .options(selectinload(MeterCommand.command_template))
        .where(CommandTemplate.category.in_(categories))
        .order_by(MeterCommand.requested_at.desc())
        .limit(limit)
    )
    if meter_id is not None:
        query = query.where(MeterCommand.meter_id == meter_id)
    if approval_filter is not None:
        query = query.where(MeterCommand.approval_status == approval_filter)

    commands = session.scalars(query).unique().all()
    return [
        _build_command_operational_recent_list_item(
            session,
            command=command,
            latest_attempt=_load_latest_command_attempt(session, command_id=command.id),
        )
        for command in commands
    ]


def _build_command_operational_detail_result(
    session: Session,
    *,
    command: MeterCommand,
    latest_attempt: CommandExecutionAttempt | None,
    unsupported_detail: str,
) -> CommandOperationalDetailResult:
    projection = _build_command_operational_projection(
        session,
        command=command,
        latest_attempt=latest_attempt,
        unsupported_detail=unsupported_detail,
    )
    return CommandOperationalDetailResult(
        command_id=command.id,
        command_family=projection["command_family"],
        command_category=command.command_template.category,
        command_status=command.current_status,
        approval_status=command.approval_status,
        approval_reviewed_at=command.approval_reviewed_at,
        approval_reviewed_by_user_id=command.approval_reviewed_by_user_id,
        approval_notes=command.approval_notes,
        meter_id=command.meter_id,
        command_template_code=command.command_template.code,
        latest_command_execution_attempt_id=latest_attempt.id if latest_attempt is not None else None,
        latest_command_execution_attempt_status=latest_attempt.status
        if latest_attempt is not None
        else None,
        runtime_execution_record_id=projection["runtime_execution_record_id"],
        family_specific_outcome_summary=projection["family_specific_outcome_summary"],
        orchestration_artifact_present=projection["orchestration_artifact_present"],
        terminalization_artifact_present=projection["terminalization_artifact_present"],
        execute_now_artifact_present=projection["execute_now_artifact_present"],
        created_at=command.created_at,
        latest_updated_at=command.updated_at,
        projection_record=projection["projection_record"],
    )


def _build_command_operational_recent_list_item(
    session: Session,
    *,
    command: MeterCommand,
    latest_attempt: CommandExecutionAttempt | None,
) -> CommandOperationalRecentListItem:
    projection = _build_command_operational_projection(
        session,
        command=command,
        latest_attempt=latest_attempt,
        unsupported_detail="Selected command is not compatible with the commands operational recent-list read-model slice.",
    )
    return CommandOperationalRecentListItem(
        command_id=command.id,
        command_family=projection["command_family"],
        command_category=command.command_template.category,
        command_status=command.current_status,
        approval_status=command.approval_status,
        approval_reviewed_at=command.approval_reviewed_at,
        approval_notes=command.approval_notes,
        meter_id=command.meter_id,
        command_template_code=command.command_template.code,
        latest_command_execution_attempt_id=latest_attempt.id if latest_attempt is not None else None,
        latest_command_execution_attempt_status=latest_attempt.status
        if latest_attempt is not None
        else None,
        runtime_execution_record_id=projection["runtime_execution_record_id"],
        family_specific_outcome_summary=projection["family_specific_outcome_summary"],
        orchestration_artifact_present=projection["orchestration_artifact_present"],
        terminalization_artifact_present=projection["terminalization_artifact_present"],
        execute_now_artifact_present=projection["execute_now_artifact_present"],
        created_at=command.created_at,
        latest_updated_at=command.updated_at,
    )


def _build_command_operational_projection(
    session: Session,
    *,
    command: MeterCommand,
    latest_attempt: CommandExecutionAttempt | None,
    unsupported_detail: str,
) -> dict[str, object]:
    category = command.command_template.category

    if category == CommandCategory.PROFILE_CAPTURE:
        status_result = get_profile_capture_execution_status(session, command_id=command.id).result
        family_specific_outcome_summary = {
            "terminal_status_category": status_result.terminal_status_category,
        }
        return {
            "command_family": CommandOperationalFamily.PROFILE_CAPTURE,
            "runtime_execution_record_id": status_result.runtime_profile_read_execution_record_id,
            "family_specific_outcome_summary": family_specific_outcome_summary,
            "orchestration_artifact_present": status_result.orchestration_artifact_present,
            "terminalization_artifact_present": status_result.terminalization_artifact_present,
            "execute_now_artifact_present": status_result.execute_now_artifact_present,
            "projection_record": {
                "command_family": CommandOperationalFamily.PROFILE_CAPTURE.value,
                "command_category": category.value,
                "command_status": command.current_status.value,
                "latest_command_execution_attempt_id": str(latest_attempt.id)
                if latest_attempt is not None
                else None,
                "latest_command_execution_attempt_status": latest_attempt.status.value
                if latest_attempt is not None
                else None,
                "runtime_execution_record_id": status_result.runtime_profile_read_execution_record_id,
                "family_specific_outcome_summary": family_specific_outcome_summary,
                "orchestration_artifact_present": status_result.orchestration_artifact_present,
                "terminalization_artifact_present": status_result.terminalization_artifact_present,
                "execute_now_artifact_present": status_result.execute_now_artifact_present,
            },
        }

    if category in {
        CommandCategory.REMOTE_DISCONNECT,
        CommandCategory.REMOTE_RECONNECT,
    }:
        status_result = get_relay_control_execution_status(session, command_id=command.id).result
        family_specific_outcome_summary = {
            "relay_control_operation": (
                status_result.relay_control_operation.value
                if status_result.relay_control_operation is not None
                else None
            ),
            "relay_control_execution_outcome": status_result.relay_control_execution_outcome,
        }
        return {
            "command_family": CommandOperationalFamily.RELAY_CONTROL,
            "runtime_execution_record_id": status_result.runtime_relay_control_execution_record_id,
            "family_specific_outcome_summary": family_specific_outcome_summary,
            "orchestration_artifact_present": status_result.orchestration_artifact_present,
            "terminalization_artifact_present": status_result.terminalization_artifact_present,
            "execute_now_artifact_present": status_result.execute_now_artifact_present,
            "projection_record": {
                "command_family": CommandOperationalFamily.RELAY_CONTROL.value,
                "command_category": category.value,
                "command_status": command.current_status.value,
                "latest_command_execution_attempt_id": str(latest_attempt.id)
                if latest_attempt is not None
                else None,
                "latest_command_execution_attempt_status": latest_attempt.status.value
                if latest_attempt is not None
                else None,
                "runtime_execution_record_id": status_result.runtime_relay_control_execution_record_id,
                "family_specific_outcome_summary": family_specific_outcome_summary,
                "orchestration_artifact_present": status_result.orchestration_artifact_present,
                "terminalization_artifact_present": status_result.terminalization_artifact_present,
                "execute_now_artifact_present": status_result.execute_now_artifact_present,
            },
        }

    if category == CommandCategory.ON_DEMAND_READ:
        status_result = get_on_demand_read_execution_status(session, command_id=command.id).result
        family_specific_outcome_summary = {
            "on_demand_read_operation": (
                status_result.on_demand_read_operation.value
                if status_result.on_demand_read_operation is not None
                else None
            ),
            "snapshot_type": (
                status_result.snapshot_type.value
                if status_result.snapshot_type is not None
                else None
            ),
            "on_demand_read_execution_outcome": status_result.on_demand_read_execution_outcome,
        }
        return {
            "command_family": CommandOperationalFamily.ON_DEMAND_READ,
            "runtime_execution_record_id": status_result.runtime_on_demand_read_execution_record_id,
            "family_specific_outcome_summary": family_specific_outcome_summary,
            "orchestration_artifact_present": status_result.orchestration_artifact_present,
            "terminalization_artifact_present": status_result.terminalization_artifact_present,
            "execute_now_artifact_present": status_result.execute_now_artifact_present,
            "projection_record": {
                "command_family": CommandOperationalFamily.ON_DEMAND_READ.value,
                "command_category": category.value,
                "command_status": command.current_status.value,
                "latest_command_execution_attempt_id": str(latest_attempt.id)
                if latest_attempt is not None
                else None,
                "latest_command_execution_attempt_status": latest_attempt.status.value
                if latest_attempt is not None
                else None,
                "runtime_execution_record_id": status_result.runtime_on_demand_read_execution_record_id,
                "family_specific_outcome_summary": family_specific_outcome_summary,
                "orchestration_artifact_present": status_result.orchestration_artifact_present,
                "terminalization_artifact_present": status_result.terminalization_artifact_present,
                "execute_now_artifact_present": status_result.execute_now_artifact_present,
            },
        }

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=unsupported_detail,
    )


def _resolve_supported_categories(
    family_filter: CommandOperationalFamily | None,
) -> tuple[CommandCategory, ...]:
    if family_filter == CommandOperationalFamily.PROFILE_CAPTURE:
        return (CommandCategory.PROFILE_CAPTURE,)
    if family_filter == CommandOperationalFamily.RELAY_CONTROL:
        return (
            CommandCategory.REMOTE_DISCONNECT,
            CommandCategory.REMOTE_RECONNECT,
        )
    if family_filter == CommandOperationalFamily.ON_DEMAND_READ:
        return (CommandCategory.ON_DEMAND_READ,)
    return (
        CommandCategory.PROFILE_CAPTURE,
        CommandCategory.REMOTE_DISCONNECT,
        CommandCategory.REMOTE_RECONNECT,
        CommandCategory.ON_DEMAND_READ,
    )
