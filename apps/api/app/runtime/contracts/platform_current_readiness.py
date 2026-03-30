from __future__ import annotations

from pydantic import BaseModel, Field

from app.runtime.contracts.platform_readiness import PlatformReadinessStatus


class PlatformCurrentReadinessComponent(BaseModel):
    name: str
    status: PlatformReadinessStatus
    ready: bool
    checked_at: str
    summary: str


class PlatformCurrentReadinessResult(BaseModel):
    service_name: str
    status: PlatformReadinessStatus
    ready: bool
    checked_at: str
    summary: str
    components: list[PlatformCurrentReadinessComponent] = Field(default_factory=list)
