from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.schemas import AuditLogListResponse
from app.modules.audit.service import list_audit_logs
from app.modules.auth.dependencies import require_permission
from app.modules.users.models import User

audit_logs_router = APIRouter(prefix="/audit-logs", tags=["audit"])


@audit_logs_router.get("", response_model=AuditLogListResponse)
def list_audit_logs_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    from_created_at: datetime | None = Query(default=None),
    to_created_at: datetime | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("audit.read")),
) -> AuditLogListResponse:
    return list_audit_logs(
        session,
        offset=offset,
        limit=limit,
        action=action,
        actor=actor,
        entity_type=entity_type,
        outcome=outcome,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
    )
