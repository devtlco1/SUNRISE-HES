from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime import api as runtime_api_module
from app.runtime.contracts import (
    DatabaseReadinessDetailResult,
    PlatformReadinessStatus,
    PlatformStartupReadinessComponent,
    PlatformStartupReadinessResult,
    RedisTransportReadinessResult,
    RedisTransportReadinessStatus,
)
from app.runtime.services import platform_startup_readiness as startup_readiness_service


def test_platform_startup_readiness_reports_ready_when_startup_snapshots_are_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        startup_readiness_service,
        "get_redis_transport_startup_readiness_snapshot",
        lambda app: RedisTransportReadinessResult(
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
        startup_readiness_service,
        "get_database_startup_readiness_snapshot",
        lambda app: DatabaseReadinessDetailResult(
            status="ready",
            ready=True,
            database_url_configured=True,
            database_reachable=True,
            ping_succeeded=True,
            checked_at="2026-03-28T00:00:01+00:00",
            summary="Database readiness is satisfied.",
        ),
    )

    result = startup_readiness_service.get_platform_startup_readiness(app)

    assert result.status == "ready"
    assert result.ready is True
    assert [component.name for component in result.components] == [
        "redis_transport_startup",
        "database_startup",
    ]


def test_platform_startup_readiness_reports_unavailable_when_one_snapshot_is_unhealthy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        startup_readiness_service,
        "get_redis_transport_startup_readiness_snapshot",
        lambda app: RedisTransportReadinessResult(
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
        startup_readiness_service,
        "get_database_startup_readiness_snapshot",
        lambda app: DatabaseReadinessDetailResult(
            status="unavailable",
            ready=False,
            database_url_configured=True,
            database_reachable=False,
            ping_succeeded=False,
            checked_at="2026-03-28T00:00:01+00:00",
            summary="Database readiness is unavailable because the database could not be reached.",
        ),
    )

    result = startup_readiness_service.get_platform_startup_readiness(app)

    assert result.status == "unavailable"
    assert result.ready is False


def test_internal_platform_startup_readiness_route_returns_both_components(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_startup_readiness",
        lambda app: PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:01+00:00",
            summary="Platform startup readiness snapshots are satisfied.",
            components=[
                PlatformStartupReadinessComponent(
                    name="redis_transport_startup",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary="Redis transport readiness is satisfied.",
                ),
                PlatformStartupReadinessComponent(
                    name="database_startup",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:00:01+00:00",
                    summary="Database readiness is satisfied.",
                ),
            ],
        ),
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/startup-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert [component["name"] for component in result["components"]] == [
        "redis_transport_startup",
        "database_startup",
    ]
