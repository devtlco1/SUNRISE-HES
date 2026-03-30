from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings
from app.runtime.contracts import (
    PlatformReadinessStatus,
    PlatformStartupReadinessComponent,
    PlatformStartupReadinessResult,
)
from app.runtime.services.database_readiness import get_database_startup_readiness_snapshot
from app.runtime.services.platform_readiness import _map_transport_status
from app.runtime.services.redis_queue_readiness import (
    get_redis_transport_startup_readiness_snapshot,
)


def get_platform_startup_readiness(app: FastAPI) -> PlatformStartupReadinessResult:
    redis_snapshot = get_redis_transport_startup_readiness_snapshot(app)
    database_snapshot = get_database_startup_readiness_snapshot(app)
    components = [
        PlatformStartupReadinessComponent(
            name="redis_transport_startup",
            status=_map_transport_status(redis_snapshot.status),
            ready=redis_snapshot.ready,
            checked_at=redis_snapshot.checked_at,
            summary=redis_snapshot.summary,
        ),
        PlatformStartupReadinessComponent(
            name="database_startup",
            status=_map_database_status(database_snapshot.status.value),
            ready=database_snapshot.ready,
            checked_at=database_snapshot.checked_at,
            summary=database_snapshot.summary,
        ),
    ]
    status = _summarize_platform_startup_status(components)
    return PlatformStartupReadinessResult(
        service_name=settings.project_name,
        status=status,
        ready=all(component.ready for component in components),
        checked_at=max(component.checked_at for component in components),
        summary=_build_platform_startup_summary(status=status),
        components=components,
    )


def _map_database_status(detail_status: str) -> PlatformReadinessStatus:
    if detail_status == PlatformReadinessStatus.READY.value:
        return PlatformReadinessStatus.READY
    if detail_status == PlatformReadinessStatus.UNAVAILABLE.value:
        return PlatformReadinessStatus.UNAVAILABLE
    return PlatformReadinessStatus.DEGRADED


def _summarize_platform_startup_status(
    components: list[PlatformStartupReadinessComponent],
) -> PlatformReadinessStatus:
    if any(component.status == PlatformReadinessStatus.UNAVAILABLE for component in components):
        return PlatformReadinessStatus.UNAVAILABLE
    if any(component.status == PlatformReadinessStatus.DEGRADED for component in components):
        return PlatformReadinessStatus.DEGRADED
    return PlatformReadinessStatus.READY


def _build_platform_startup_summary(*, status: PlatformReadinessStatus) -> str:
    if status == PlatformReadinessStatus.READY:
        return "Platform startup readiness snapshots are satisfied."
    if status == PlatformReadinessStatus.UNAVAILABLE:
        return (
            "Platform startup readiness snapshots are unavailable because a required "
            "dependency could not be reached at startup."
        )
    return (
        "Platform startup readiness snapshots are degraded because a required "
        "dependency was not fully ready at startup."
    )
