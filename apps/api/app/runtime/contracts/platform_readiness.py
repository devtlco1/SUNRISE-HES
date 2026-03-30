from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class PlatformReadinessStatus(StringEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class PlatformReadinessComponent(BaseModel):
    name: str
    status: PlatformReadinessStatus
    ready: bool
    summary: str


class PlatformReadinessResult(BaseModel):
    service_name: str
    status: PlatformReadinessStatus
    ready: bool
    checked_at: str
    summary: str
    components: list[PlatformReadinessComponent] = Field(default_factory=list)
