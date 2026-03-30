from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime import api as runtime_api_module
from app.runtime.contracts import (
    DatabaseReadinessDetailResult,
    PlatformCurrentReadinessComponent,
    PlatformCurrentReadinessResult,
    PlatformReadinessStatus,
    PlatformStartupReadinessComponent,
    PlatformStartupReadinessResult,
    RedisTransportReadinessResult,
    RedisTransportReadinessStatus,
)
from app.runtime.services import platform_current_readiness as current_readiness_service


def test_platform_current_readiness_reports_ready_when_current_dependencies_are_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        current_readiness_service,
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
        current_readiness_service,
        "get_database_readiness_detail",
        lambda: DatabaseReadinessDetailResult(
            status="ready",
            ready=True,
            database_url_configured=True,
            database_reachable=True,
            ping_succeeded=True,
            checked_at="2026-03-28T00:00:01+00:00",
            summary="Database readiness is satisfied.",
        ),
    )

    result = current_readiness_service.get_platform_current_readiness()

    assert result.status == "ready"
    assert result.ready is True
    assert [component.name for component in result.components] == [
        "redis_transport_current",
        "database_current",
    ]


def test_platform_current_readiness_reports_unavailable_when_one_dependency_is_unhealthy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        current_readiness_service,
        "evaluate_redis_transport_readiness",
        lambda *, apply_startup_policy: RedisTransportReadinessResult(
            status=RedisTransportReadinessStatus.UNAVAILABLE,
            ready=False,
            validate_on_startup=True,
            ensure_stream_on_startup=False,
            ensure_consumer_group_on_startup=False,
            validation_performed=True,
            bootstrap_applied=False,
            redis_reachable=False,
            stream_name="hes:dispatch",
            stream_ready=False,
            consumer_group_name="hes-worker-group",
            consumer_group_ready=False,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Redis transport readiness could not reach Redis.",
        ),
    )
    monkeypatch.setattr(
        current_readiness_service,
        "get_database_readiness_detail",
        lambda: DatabaseReadinessDetailResult(
            status="ready",
            ready=True,
            database_url_configured=True,
            database_reachable=True,
            ping_succeeded=True,
            checked_at="2026-03-28T00:00:01+00:00",
            summary="Database readiness is satisfied.",
        ),
    )

    result = current_readiness_service.get_platform_current_readiness()

    assert result.status == "unavailable"
    assert result.ready is False


def test_internal_platform_current_readiness_route_returns_both_components(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_current_readiness",
        lambda: PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:01+00:00",
            summary="Platform current readiness is satisfied.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary="Redis transport readiness is satisfied.",
                ),
                PlatformCurrentReadinessComponent(
                    name="database_current",
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
        "/api/v1/internal/platform/current-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert [component["name"] for component in result["components"]] == [
        "redis_transport_current",
        "database_current",
    ]


def test_current_and_startup_summary_routes_remain_distinct(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_current_readiness",
        lambda: PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:01+00:00",
            summary="Platform current readiness is satisfied.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary="Redis transport readiness is satisfied.",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_startup_readiness",
        lambda app: PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are unavailable.",
            components=[
                PlatformStartupReadinessComponent(
                    name="redis_transport_startup",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary="Redis transport readiness could not reach Redis.",
                )
            ],
        ),
    )
    client = TestClient(app)

    current_response = client.get(
        "/api/v1/internal/platform/current-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    startup_response = client.get(
        "/api/v1/internal/platform/startup-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert current_response.status_code == 200
    assert startup_response.status_code == 200
    assert current_response.json()["result"]["status"] == "ready"
    assert startup_response.json()["result"]["status"] == "unavailable"
