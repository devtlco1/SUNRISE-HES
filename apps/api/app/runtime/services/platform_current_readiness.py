from __future__ import annotations

from app.core.config import settings
from app.runtime.contracts import (
    PlatformCurrentReadinessComponent,
    PlatformCurrentReadinessResult,
    PlatformReadinessStatus,
)
from app.runtime.services.database_readiness import get_database_readiness_detail
from app.runtime.services.platform_readiness import _map_transport_status
from app.runtime.services.platform_startup_readiness import (
    _build_platform_startup_summary,
    _map_database_status,
    _summarize_platform_startup_status,
)
from app.runtime.services.redis_queue_readiness import evaluate_redis_transport_readiness


def get_platform_current_readiness() -> PlatformCurrentReadinessResult:
    redis_readiness = evaluate_redis_transport_readiness(apply_startup_policy=False)
    database_readiness = get_database_readiness_detail()
    components = [
        PlatformCurrentReadinessComponent(
            name="redis_transport_current",
            status=_map_transport_status(redis_readiness.status),
            ready=redis_readiness.ready,
            checked_at=redis_readiness.checked_at,
            summary=redis_readiness.summary,
        ),
        PlatformCurrentReadinessComponent(
            name="database_current",
            status=_map_database_status(database_readiness.status.value),
            ready=database_readiness.ready,
            checked_at=database_readiness.checked_at,
            summary=database_readiness.summary,
        ),
    ]
    status = _summarize_current_status(components)
    return PlatformCurrentReadinessResult(
        service_name=settings.project_name,
        status=status,
        ready=all(component.ready for component in components),
        checked_at=max(component.checked_at for component in components),
        summary=_build_current_summary(status=status),
        components=components,
    )


def _summarize_current_status(
    components: list[PlatformCurrentReadinessComponent],
) -> PlatformReadinessStatus:
    return _summarize_platform_startup_status(components)


def _build_current_summary(*, status: PlatformReadinessStatus) -> str:
    startup_style_summary = _build_platform_startup_summary(status=status)
    return startup_style_summary.replace("startup readiness snapshots", "current readiness")
