from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class AuditPayloadSchema(BaseModel):
    outcome: str
    http: dict[str, str | None]
    details: dict[str, object] | None = None


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    request_id: str | None
    ip_address: str | None
    description: str | None
    payload: AuditPayloadSchema | None
