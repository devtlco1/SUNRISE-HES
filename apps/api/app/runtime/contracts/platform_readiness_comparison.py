from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.platform_readiness import PlatformReadinessStatus


class PlatformReadinessDeltaStatus(StringEnum):
    UNCHANGED = "unchanged"
    REGRESSED = "regressed"
    RECOVERED = "recovered"
    CHANGED = "changed"


class PlatformReadinessComparisonComponent(BaseModel):
    name: str
    startup_status: PlatformReadinessStatus
    current_status: PlatformReadinessStatus
    delta_status: PlatformReadinessDeltaStatus
    startup_checked_at: str
    current_checked_at: str
    startup_summary: str
    current_summary: str


class PlatformReadinessComparisonResult(BaseModel):
    service_name: str
    startup_status: PlatformReadinessStatus
    current_status: PlatformReadinessStatus
    delta_status: PlatformReadinessDeltaStatus
    ready: bool
    compared_at: str
    summary: str
    components: list[PlatformReadinessComparisonComponent] = Field(default_factory=list)
