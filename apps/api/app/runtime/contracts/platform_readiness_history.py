from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.runtime.contracts.platform_readiness import PlatformReadinessStatus
from app.runtime.contracts.platform_readiness_comparison import PlatformReadinessDeltaStatus


class PlatformReadinessHistoryEventKind(StringEnum):
    STARTUP_SUMMARY = "startup_summary"
    CURRENT_SUMMARY = "current_summary"
    COMPARISON = "comparison"


class PlatformReadinessHistoryComponentSnapshot(BaseModel):
    name: str
    status: PlatformReadinessStatus
    ready: bool
    summary: str
    delta_status: PlatformReadinessDeltaStatus | None = None


class PlatformReadinessHistoryEvent(BaseModel):
    event_kind: PlatformReadinessHistoryEventKind
    recorded_at: str
    status: PlatformReadinessStatus
    ready: bool
    summary: str
    component_count: int
    delta_status: PlatformReadinessDeltaStatus | None = None
    components: list[PlatformReadinessHistoryComponentSnapshot] = Field(default_factory=list)


class PlatformReadinessHistoryResult(BaseModel):
    total: int
    items: list[PlatformReadinessHistoryEvent] = Field(default_factory=list)
