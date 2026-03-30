from __future__ import annotations

from app.runtime.contracts import (
    PlatformReadinessStatus,
    RedisTransportReadinessResult,
    RedisTransportReadinessStatus,
)
from app.runtime.services import platform_readiness as platform_readiness_service


def test_platform_readiness_reports_ready_when_redis_and_database_are_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        platform_readiness_service,
        "evaluate_redis_transport_readiness",
        lambda *, apply_startup_policy: RedisTransportReadinessResult(
            status=RedisTransportReadinessStatus.READY,
            ready=True,
            validate_on_startup=True,
            ensure_stream_on_startup=False,
            ensure_consumer_group_on_startup=False,
            validation_performed=True,
            bootstrap_applied=False,
            redis_reachable=True,
            stream_name="hes:dispatch",
            stream_ready=True,
            consumer_group_name="hes-worker-group",
            consumer_group_ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Redis transport readiness is satisfied.",
        ),
    )
    monkeypatch.setattr(
        platform_readiness_service,
        "evaluate_database_readiness",
        lambda: platform_readiness_service.PlatformReadinessComponent(
            name="database",
            status=PlatformReadinessStatus.READY,
            ready=True,
            summary="Database readiness is satisfied.",
        ),
    )

    result = platform_readiness_service.get_platform_readiness()

    assert result.service_name
    assert result.status == "ready"
    assert result.ready is True
    assert len(result.components) == 2
    assert result.components[0].name == "redis_transport"
    assert result.components[0].status == "ready"
    assert result.components[1].name == "database"
    assert result.components[1].status == "ready"


def test_platform_readiness_reports_unavailable_when_database_is_not_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        platform_readiness_service,
        "evaluate_redis_transport_readiness",
        lambda *, apply_startup_policy: RedisTransportReadinessResult(
            status=RedisTransportReadinessStatus.READY,
            ready=True,
            validate_on_startup=True,
            ensure_stream_on_startup=False,
            ensure_consumer_group_on_startup=False,
            validation_performed=True,
            bootstrap_applied=False,
            redis_reachable=True,
            stream_name="hes:dispatch",
            stream_ready=True,
            consumer_group_name="hes-worker-group",
            consumer_group_ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Redis transport readiness is satisfied.",
        ),
    )
    monkeypatch.setattr(
        platform_readiness_service,
        "evaluate_database_readiness",
        lambda: platform_readiness_service.PlatformReadinessComponent(
            name="database",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            summary="Database readiness is unavailable because the database could not be reached.",
        ),
    )

    result = platform_readiness_service.get_platform_readiness()

    assert result.status == "unavailable"
    assert result.ready is False
    assert [component.name for component in result.components] == [
        "redis_transport",
        "database",
    ]
