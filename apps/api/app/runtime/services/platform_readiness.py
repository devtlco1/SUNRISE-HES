from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings
from app.runtime.contracts import (
    PlatformReadinessComponent,
    PlatformReadinessResult,
    PlatformReadinessStatus,
    RedisTransportReadinessStatus,
)
from app.runtime.services.database_readiness import evaluate_database_readiness
from app.runtime.services.redis_queue_readiness import evaluate_redis_transport_readiness


def get_platform_readiness() -> PlatformReadinessResult:
    redis_transport = evaluate_redis_transport_readiness(apply_startup_policy=False)
    components = [
        _build_redis_transport_component(
            redis_transport.status, redis_transport.ready, redis_transport.summary
        ),
        evaluate_database_readiness(),
    ]
    ready = all(component.ready for component in components)
    status = _summarize_platform_status(components)
    return PlatformReadinessResult(
        service_name=settings.project_name,
        status=status,
        ready=ready,
        checked_at=datetime.now(UTC).isoformat(),
        summary=_build_platform_summary(status=status),
        components=components,
    )


def _build_redis_transport_component(
    transport_status: RedisTransportReadinessStatus,
    ready: bool,
    summary: str,
) -> PlatformReadinessComponent:
    component_status = _map_transport_status(transport_status)
    return PlatformReadinessComponent(
        name="redis_transport",
        status=component_status,
        ready=ready,
        summary=summary,
    )


def _map_transport_status(
    transport_status: RedisTransportReadinessStatus,
) -> PlatformReadinessStatus:
    if transport_status == RedisTransportReadinessStatus.READY:
        return PlatformReadinessStatus.READY
    if transport_status == RedisTransportReadinessStatus.UNAVAILABLE:
        return PlatformReadinessStatus.UNAVAILABLE
    return PlatformReadinessStatus.DEGRADED


def _summarize_platform_status(
    components: list[PlatformReadinessComponent],
) -> PlatformReadinessStatus:
    if any(component.status == PlatformReadinessStatus.UNAVAILABLE for component in components):
        return PlatformReadinessStatus.UNAVAILABLE
    if any(component.status == PlatformReadinessStatus.DEGRADED for component in components):
        return PlatformReadinessStatus.DEGRADED
    return PlatformReadinessStatus.READY


def _build_platform_summary(*, status: PlatformReadinessStatus) -> str:
    if status == PlatformReadinessStatus.READY:
        return "Platform readiness is satisfied."
    if status == PlatformReadinessStatus.UNAVAILABLE:
        return "Platform readiness is unavailable because a required dependency is unreachable."
    return "Platform readiness is degraded because a required dependency is not fully ready."
