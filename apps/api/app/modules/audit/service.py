from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.context import RequestAuditContext, get_request_context
from app.modules.audit.helpers import build_audit_payload
from app.modules.audit.models import AuditLog


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
