from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.audit.context import RequestAuditContext, get_request_context
from app.modules.audit.helpers import build_audit_payload
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditLogListResponse, AuditLogResponse
from app.modules.users.models import User


def record_audit_event(
    session: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    outcome: str = "success",
    description: str | None = None,
    details: dict[str, Any] | None = None,
    request_context: RequestAuditContext | None = None,
) -> AuditLog:
    context = request_context or get_request_context()
    context_details = {
        "method": context.method if context else None,
        "path": context.path if context else None,
        "user_agent": context.user_agent if context else None,
    }
    audit_log = AuditLog(
        actor_user_id=actor_user_id or (context.actor_user_id if context else None),
        action=action,
        entity_type=resource_type,
        entity_id=resource_id,
        request_id=context.request_id if context else None,
        ip_address=context.ip_address if context else None,
        description=description,
        payload=build_audit_payload(
            outcome=outcome,
            context_details=context_details,
            details=details,
        ),
    )
    session.add(audit_log)
    session.commit()
    session.refresh(audit_log)
    return audit_log


def list_audit_logs(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    action: str | None = None,
    actor: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    outcome: str | None = None,
    from_created_at: datetime | None = None,
    to_created_at: datetime | None = None,
) -> AuditLogListResponse:
    filters = _build_audit_log_filters(
        action=action,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        outcome=outcome,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
    )
    base_statement = (
        select(
            AuditLog,
            User.username.label("actor_username"),
            User.full_name.label("actor_full_name"),
        )
        .outerjoin(User, AuditLog.actor_user_id == User.id)
        .where(*filters)
    )
    total = session.scalar(
        select(func.count()).select_from(base_statement.with_only_columns(AuditLog.id).subquery())
    ) or 0
    rows = session.execute(
        base_statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return AuditLogListResponse(
        total=total,
        items=[
            AuditLogResponse(
                id=audit_log.id,
                created_at=audit_log.created_at,
                actor_user_id=audit_log.actor_user_id,
                actor_username=actor_username,
                actor_full_name=actor_full_name,
                action=audit_log.action,
                entity_type=audit_log.entity_type,
                entity_id=audit_log.entity_id,
                request_id=audit_log.request_id,
                ip_address=audit_log.ip_address,
                description=audit_log.description,
                payload=audit_log.payload,
            )
            for audit_log, actor_username, actor_full_name in rows
        ],
    )


def _build_audit_log_filters(
    *,
    action: str | None,
    actor: str | None,
    entity_type: str | None,
    entity_id: UUID | None,
    outcome: str | None,
    from_created_at: datetime | None,
    to_created_at: datetime | None,
) -> list[Any]:
    filters: list[Any] = []
    if action:
        filters.append(AuditLog.action.ilike(f"%{action.strip()}%"))
    if actor:
        actor_value = actor.strip()
        filters.append(
            or_(
                User.username.ilike(f"%{actor_value}%"),
                User.full_name.ilike(f"%{actor_value}%"),
            )
        )
    if entity_type:
        filters.append(AuditLog.entity_type.ilike(f"%{entity_type.strip()}%"))
    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)
    if outcome:
        filters.append(AuditLog.payload.op("->>")("outcome") == outcome.strip())
    if from_created_at is not None:
        filters.append(AuditLog.created_at >= from_created_at)
    if to_created_at is not None:
        filters.append(AuditLog.created_at <= to_created_at)
    return filters
