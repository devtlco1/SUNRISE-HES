from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditPayloadHttpSchema(BaseModel):
    method: str | None = None
    path: str | None = None
    user_agent: str | None = None


class AuditPayloadSchema(BaseModel):
    outcome: str
    http: AuditPayloadHttpSchema
    details: dict[str, object] | None = None


class AuditLogResponse(BaseModel):
    id: UUID
    created_at: datetime
    actor_user_id: UUID | None
    actor_username: str | None
    actor_full_name: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    request_id: str | None
    ip_address: str | None
    description: str | None
    payload: AuditPayloadSchema | None


class AuditLogListResponse(BaseModel):
    total: int
    items: list[AuditLogResponse]
