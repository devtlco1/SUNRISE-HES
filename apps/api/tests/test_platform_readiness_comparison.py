from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime import api as runtime_api_module
from app.runtime.contracts import (
    PlatformCurrentReadinessComponent,
    PlatformCurrentReadinessResult,
    PlatformReadinessComparisonComponent,
    PlatformReadinessComparisonResult,
    PlatformReadinessDeltaStatus,
    PlatformReadinessStatus,
    PlatformStartupReadinessComponent,
    PlatformStartupReadinessResult,
)
from app.runtime.services import (
    platform_readiness_comparison as comparison_service,
)


def test_platform_readiness_comparison_reports_unchanged_when_states_match(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        comparison_service,
        "get_platform_startup_readiness",
        lambda app: PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
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
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary="Database readiness is satisfied.",
                ),
            ],
        ),
    )
    monkeypatch.setattr(
        comparison_service,
        "get_platform_current_readiness",
        lambda: PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is satisfied.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Redis transport readiness is satisfied.",
                ),
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is satisfied.",
                ),
            ],
        ),
    )

    result = comparison_service.get_platform_readiness_comparison(app)

    assert result.delta_status == PlatformReadinessDeltaStatus.UNCHANGED
    assert [component.delta_status for component in result.components] == [
        PlatformReadinessDeltaStatus.UNCHANGED,
        PlatformReadinessDeltaStatus.UNCHANGED,
    ]


def test_platform_readiness_comparison_reports_regressed_when_dependency_worsens(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        comparison_service,
        "get_platform_startup_readiness",
        lambda app: PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are satisfied.",
            components=[
                PlatformStartupReadinessComponent(
                    name="redis_transport_startup",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary="Redis transport readiness is satisfied.",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        comparison_service,
        "get_platform_current_readiness",
        lambda: PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Redis transport readiness could not reach Redis.",
                )
            ],
        ),
    )

    result = comparison_service.get_platform_readiness_comparison(app)

    assert result.delta_status == PlatformReadinessDeltaStatus.REGRESSED
    assert result.components[0].delta_status == PlatformReadinessDeltaStatus.REGRESSED


def test_platform_readiness_comparison_reports_recovered_when_dependency_recovers(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        comparison_service,
        "get_platform_startup_readiness",
        lambda app: PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are unavailable.",
            components=[
                PlatformStartupReadinessComponent(
                    name="database_startup",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary=(
                        "Database readiness is unavailable because the database could "
                        "not be reached."
                    ),
                )
            ],
        ),
    )
    monkeypatch.setattr(
        comparison_service,
        "get_platform_current_readiness",
        lambda: PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is satisfied.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is satisfied.",
                )
            ],
        ),
    )

    result = comparison_service.get_platform_readiness_comparison(app)

    assert result.delta_status == PlatformReadinessDeltaStatus.RECOVERED
    assert result.components[0].delta_status == PlatformReadinessDeltaStatus.RECOVERED


def test_internal_platform_readiness_comparison_route_returns_both_components(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_comparison",
        lambda app: PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.UNAVAILABLE,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:01:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.UNAVAILABLE,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:01:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness could not reach Redis.",
                ),
                PlatformReadinessComparisonComponent(
                    name="database",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.READY,
                    delta_status=PlatformReadinessDeltaStatus.UNCHANGED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:01:00+00:00",
                    startup_summary="Database readiness is satisfied.",
                    current_summary="Database readiness is satisfied.",
                ),
            ],
        ),
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-comparison",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert [component["name"] for component in result["components"]] == [
        "redis_transport",
        "database",
    ]


def test_current_and_startup_summary_routes_remain_unchanged_with_comparison_surface(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_current_readiness",
        lambda: PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is satisfied.",
            components=[],
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
            components=[],
        ),
    )
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_comparison",
        lambda app: PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.UNAVAILABLE,
            current_status=PlatformReadinessStatus.READY,
            delta_status=PlatformReadinessDeltaStatus.RECOVERED,
            ready=True,
            compared_at="2026-03-28T00:01:00+00:00",
            summary="Platform readiness comparison detected dependency recovery since startup.",
            components=[],
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
    comparison_response = client.get(
        "/api/v1/internal/platform/readiness-comparison",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert current_response.status_code == 200
    assert startup_response.status_code == 200
    assert comparison_response.status_code == 200
    assert current_response.json()["result"]["status"] == "ready"
    assert startup_response.json()["result"]["status"] == "unavailable"
    assert comparison_response.json()["result"]["delta_status"] == "recovered"
