from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum


class DatabaseReadinessDetailStatus(StringEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class DatabaseReadinessDetailResult(BaseModel):
    status: DatabaseReadinessDetailStatus
    ready: bool
    database_url_configured: bool
    database_reachable: bool
    ping_succeeded: bool
    checked_at: str
    summary: str
