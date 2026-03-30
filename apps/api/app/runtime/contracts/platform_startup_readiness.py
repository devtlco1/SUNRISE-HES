from __future__ import annotations

from pydantic import BaseModel, Field

from app.runtime.contracts.platform_readiness import PlatformReadinessStatus


class PlatformStartupReadinessComponent(BaseModel):
    name: str
    status: PlatformReadinessStatus
    ready: bool
    checked_at: str
    summary: str


class PlatformStartupReadinessResult(BaseModel):
    service_name: str
    status: PlatformReadinessStatus
    ready: bool
    checked_at: str
    summary: str
    components: list[PlatformStartupReadinessComponent] = Field(default_factory=list)
