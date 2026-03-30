from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main as app_main_module
from app.core.config import settings
from app.main import app
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime import api as runtime_api_module
from app.runtime.contracts import (
    DatabaseReadinessDetailResult,
    PlatformCurrentReadinessComponent,
    PlatformCurrentReadinessResult,
    PlatformReadinessComparisonComponent,
    PlatformReadinessComparisonResult,
    PlatformReadinessDeltaStatus,
    PlatformReadinessHistoryComponentSnapshot,
    PlatformReadinessHistoryEvent,
    PlatformReadinessHistoryEventKind,
    PlatformReadinessHistoryResult,
    PlatformReadinessStatus,
    PlatformStartupReadinessComponent,
    PlatformStartupReadinessResult,
    RedisTransportReadinessResult,
    RedisTransportReadinessStatus,
)
from app.runtime.services import platform_readiness_history as history_service


def test_readiness_history_records_startup_current_and_comparison_events(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        app_main_module,
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
        app_main_module,
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
    monkeypatch.setattr(
        runtime_api_module,
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
                )
            ],
        ),
    )
    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_comparison",
        lambda app: PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.READY,
            delta_status=PlatformReadinessDeltaStatus.UNCHANGED,
            ready=True,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison found no dependency state changes.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.READY,
                    delta_status=PlatformReadinessDeltaStatus.UNCHANGED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:01:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness is satisfied.",
                )
            ],
        ),
    )

    with TestClient(app) as client:
        client.get(
            "/api/v1/internal/platform/current-readiness",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        )
        client.get(
            "/api/v1/internal/platform/readiness-comparison",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        )
        history_response = client.get(
            "/api/v1/internal/platform/readiness-history",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        )

        assert history_response.status_code == 200
        items = history_response.json()["result"]["items"]
        assert [item["event_kind"] for item in items[:3]] == [
            PlatformReadinessHistoryEventKind.COMPARISON,
            PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
            PlatformReadinessHistoryEventKind.STARTUP_SUMMARY,
        ]
        assert [component["name"] for component in items[0]["components"]] == ["redis_transport"]
        assert items[0]["components"][0]["delta_status"] == "unchanged"
        assert [component["name"] for component in items[1]["components"]] == [
            "redis_transport_current"
        ]
        assert [component["name"] for component in items[2]["components"]] == [
            "redis_transport_startup",
            "database_startup",
        ]


def test_readiness_history_remains_bounded() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)

    for index in range(history_service.READINESS_HISTORY_MAX_EVENTS + 5):
        history_service.record_platform_current_readiness_event(
            history_app,
            PlatformCurrentReadinessResult(
                service_name="sunrise-hes-platform",
                status=PlatformReadinessStatus.READY,
                ready=True,
                checked_at=f"2026-03-28T00:00:{index:02d}+00:00",
                summary="Platform current readiness is satisfied.",
                components=[],
            ),
        )

    result = history_service.get_platform_readiness_history(history_app)

    assert result.total == history_service.READINESS_HISTORY_MAX_EVENTS
    assert result.items[0].recorded_at == "2026-03-28T00:00:29+00:00"


def test_readiness_history_route_returns_stable_newest_first_order(monkeypatch) -> None:
    def fake_get_platform_readiness_history(
        app,
        limit=25,
        recorded_after=None,
        recorded_before=None,
        event_kind=None,
        status=None,
        delta_status=None,
        component_name=None,
        component_delta_status=None,
        component_status=None,
        component_ready=None,
    ) -> PlatformReadinessHistoryResult:
        return PlatformReadinessHistoryResult(
            total=2,
            items=[
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.COMPARISON,
                    recorded_at="2026-03-28T00:02:00+00:00",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    summary="Platform readiness comparison found no dependency state changes.",
                    component_count=2,
                    delta_status=PlatformReadinessDeltaStatus.UNCHANGED,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name="redis_transport",
                            status=PlatformReadinessStatus.READY,
                            ready=True,
                            summary="Redis transport readiness is satisfied.",
                            delta_status=PlatformReadinessDeltaStatus.UNCHANGED,
                        )
                    ],
                ),
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.STARTUP_SUMMARY,
                    recorded_at="2026-03-28T00:00:00+00:00",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    summary="Platform startup readiness snapshots are satisfied.",
                    component_count=2,
                    delta_status=None,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name="database_startup",
                            status=PlatformReadinessStatus.READY,
                            ready=True,
                            summary="Database readiness is satisfied.",
                            delta_status=None,
                        )
                    ],
                ),
            ],
        )

    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_history",
        fake_get_platform_readiness_history,
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    items = response.json()["result"]["items"]
    assert items[0]["recorded_at"] == "2026-03-28T00:02:00+00:00"
    assert items[1]["recorded_at"] == "2026-03-28T00:00:00+00:00"


def test_readiness_history_can_filter_by_event_kind() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are satisfied.",
            components=[],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
    )

    assert result.total == 1
    assert result.items[0].event_kind == PlatformReadinessHistoryEventKind.CURRENT_SUMMARY


def test_readiness_history_can_filter_by_component_name_redis_transport() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
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
                    checked_at="2026-03-28T00:00:01+00:00",
                    summary="Database readiness is satisfied.",
                ),
            ],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.DEGRADED,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Redis transport readiness is degraded.",
                )
            ],
        ),
    )
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.DEGRADED,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:02:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness is degraded.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="redis_transport",
    )

    assert result.total == 3
    assert [item.event_kind for item in result.items] == [
        PlatformReadinessHistoryEventKind.COMPARISON,
        PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
        PlatformReadinessHistoryEventKind.STARTUP_SUMMARY,
    ]


def test_readiness_history_can_filter_by_component_name_database() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are satisfied.",
            components=[
                PlatformStartupReadinessComponent(
                    name="database_startup",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:00:00+00:00",
                    summary="Database readiness is satisfied.",
                )
            ],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="database",
    )

    assert result.total == 2
    assert [item.event_kind for item in result.items] == [
        PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
        PlatformReadinessHistoryEventKind.STARTUP_SUMMARY,
    ]


def test_readiness_history_can_filter_by_component_name_and_component_delta_status() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.DEGRADED,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:02:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness is degraded.",
                )
            ],
        ),
    )
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.UNAVAILABLE,
            current_status=PlatformReadinessStatus.READY,
            delta_status=PlatformReadinessDeltaStatus.RECOVERED,
            ready=True,
            compared_at="2026-03-28T00:03:00+00:00",
            summary="Platform readiness comparison detected dependency recovery since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="database",
                    startup_status=PlatformReadinessStatus.UNAVAILABLE,
                    current_status=PlatformReadinessStatus.READY,
                    delta_status=PlatformReadinessDeltaStatus.RECOVERED,
                    startup_checked_at="2026-03-28T00:00:01+00:00",
                    current_checked_at="2026-03-28T00:03:00+00:00",
                    startup_summary="Database readiness is unavailable.",
                    current_summary="Database readiness is satisfied.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="redis_transport",
        component_delta_status=PlatformReadinessDeltaStatus.REGRESSED,
    )

    assert result.total == 1
    assert result.items[0].components[0].name == "redis_transport"
    assert result.items[0].components[0].delta_status == PlatformReadinessDeltaStatus.REGRESSED


def test_readiness_history_can_filter_by_database_component_recovery() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.UNAVAILABLE,
            current_status=PlatformReadinessStatus.READY,
            delta_status=PlatformReadinessDeltaStatus.RECOVERED,
            ready=True,
            compared_at="2026-03-28T00:03:00+00:00",
            summary="Platform readiness comparison detected dependency recovery since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="database",
                    startup_status=PlatformReadinessStatus.UNAVAILABLE,
                    current_status=PlatformReadinessStatus.READY,
                    delta_status=PlatformReadinessDeltaStatus.RECOVERED,
                    startup_checked_at="2026-03-28T00:00:01+00:00",
                    current_checked_at="2026-03-28T00:03:00+00:00",
                    startup_summary="Database readiness is unavailable.",
                    current_summary="Database readiness is satisfied.",
                )
            ],
        ),
    )
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:04:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.DEGRADED,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:04:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness is degraded.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="database",
        component_delta_status=PlatformReadinessDeltaStatus.RECOVERED,
    )

    assert result.total == 1
    assert result.items[0].recorded_at == "2026-03-28T00:03:00+00:00"


def test_readiness_history_can_filter_by_component_name_and_component_status() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:02:00+00:00",
            summary="Platform current readiness is satisfied.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:02:00+00:00",
                    summary="Redis transport readiness is satisfied.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="database",
        component_status=PlatformReadinessStatus.UNAVAILABLE,
    )

    assert result.total == 1
    assert result.items[0].components[0].name == "database_current"


def test_readiness_history_can_filter_by_redis_component_ready_status() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
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
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.DEGRADED,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is degraded.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="redis_transport",
        component_status=PlatformReadinessStatus.READY,
    )

    assert result.total == 1
    assert result.items[0].event_kind == PlatformReadinessHistoryEventKind.STARTUP_SUMMARY


def test_readiness_history_can_filter_by_component_name_and_component_ready() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:02:00+00:00",
            summary="Platform current readiness is satisfied.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    checked_at="2026-03-28T00:02:00+00:00",
                    summary="Redis transport readiness is satisfied.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="database",
        component_ready=False,
    )

    assert result.total == 1
    assert result.items[0].components[0].name == "database_current"


def test_readiness_history_can_filter_by_recorded_after() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are satisfied.",
            components=[],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[],
        ),
    )
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        recorded_after=datetime.fromisoformat("2026-03-28T00:01:00+00:00"),
    )

    assert result.total == 2
    assert [item.recorded_at for item in result.items] == [
        "2026-03-28T00:02:00+00:00",
        "2026-03-28T00:01:00+00:00",
    ]


def test_readiness_history_can_filter_by_recorded_before() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are satisfied.",
            components=[],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[],
        ),
    )
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        recorded_before=datetime.fromisoformat("2026-03-28T00:01:00+00:00"),
    )

    assert result.total == 2
    assert [item.recorded_at for item in result.items] == [
        "2026-03-28T00:01:00+00:00",
        "2026-03-28T00:00:00+00:00",
    ]


def test_readiness_history_can_filter_by_bounded_time_window() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform startup readiness snapshots are satisfied.",
            components=[],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[],
        ),
    )
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        recorded_after=datetime.fromisoformat("2026-03-28T00:00:30+00:00"),
        recorded_before=datetime.fromisoformat("2026-03-28T00:01:30+00:00"),
    )

    assert result.total == 1
    assert result.items[0].recorded_at == "2026-03-28T00:01:00+00:00"


def test_readiness_history_can_filter_by_delta_status() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.UNAVAILABLE,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[],
        ),
    )
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.UNAVAILABLE,
            current_status=PlatformReadinessStatus.READY,
            delta_status=PlatformReadinessDeltaStatus.RECOVERED,
            ready=True,
            compared_at="2026-03-28T00:03:00+00:00",
            summary="Platform readiness comparison detected dependency recovery since startup.",
            components=[],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        delta_status=PlatformReadinessDeltaStatus.RECOVERED,
    )

    assert result.total == 1
    assert result.items[0].delta_status == PlatformReadinessDeltaStatus.RECOVERED


def test_readiness_history_can_filter_by_status() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is satisfied.",
            components=[],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:02:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        status=PlatformReadinessStatus.DEGRADED,
    )

    assert result.total == 1
    assert result.items[0].status == PlatformReadinessStatus.DEGRADED


def test_readiness_history_can_combine_component_name_with_status() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
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
                )
            ],
        ),
    )
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:02:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.DEGRADED,
                    ready=False,
                    checked_at="2026-03-28T00:02:00+00:00",
                    summary="Database readiness is degraded.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_name="database",
        status=PlatformReadinessStatus.DEGRADED,
    )

    assert result.total == 1
    assert result.items[0].components[0].name == "database_current"


def test_readiness_history_component_status_without_component_name_is_empty() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_status=PlatformReadinessStatus.UNAVAILABLE,
    )

    assert result.total == 0
    assert result.items == []


def test_readiness_history_component_ready_without_component_name_is_empty() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_ready=False,
    )

    assert result.total == 0
    assert result.items == []


def test_readiness_history_component_delta_status_without_component_name_is_empty() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.DEGRADED,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:02:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness is degraded.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        component_delta_status=PlatformReadinessDeltaStatus.REGRESSED,
    )

    assert result.total == 0
    assert result.items == []


def test_readiness_history_can_combine_component_delta_status_with_event_kind() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
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
    history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.DEGRADED,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.DEGRADED,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:02:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness is degraded.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        event_kind=PlatformReadinessHistoryEventKind.COMPARISON,
        component_name="redis_transport",
        component_delta_status=PlatformReadinessDeltaStatus.REGRESSED,
    )

    assert result.total == 1
    assert result.items[0].event_kind == PlatformReadinessHistoryEventKind.COMPARISON


def test_readiness_history_can_combine_component_status_with_event_kind() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
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
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
        component_name="database",
        component_status=PlatformReadinessStatus.UNAVAILABLE,
    )

    assert result.total == 1
    assert result.items[0].event_kind == PlatformReadinessHistoryEventKind.CURRENT_SUMMARY


def test_readiness_history_can_combine_component_ready_with_event_kind() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
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
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
        component_name="database",
        component_ready=False,
    )

    assert result.total == 1
    assert result.items[0].event_kind == PlatformReadinessHistoryEventKind.CURRENT_SUMMARY


def test_readiness_history_can_combine_time_range_with_component_filter() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)
    history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
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
    history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.UNAVAILABLE,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is unavailable.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="database_current",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Database readiness is unavailable.",
                )
            ],
        ),
    )

    result = history_service.get_platform_readiness_history(
        history_app,
        recorded_after=datetime.fromisoformat("2026-03-28T00:00:30+00:00"),
        component_name="database",
        component_ready=False,
    )

    assert result.total == 1
    assert result.items[0].components[0].name == "database_current"


def test_readiness_history_route_supports_kind_filter_and_limit(monkeypatch) -> None:
    def fake_get_platform_readiness_history(
        app,
        limit=25,
        recorded_after=None,
        recorded_before=None,
        event_kind=None,
        status=None,
        delta_status=None,
        component_name=None,
        component_delta_status=None,
        component_status=None,
        component_ready=None,
    ) -> PlatformReadinessHistoryResult:
        return PlatformReadinessHistoryResult(
            total=1,
            items=[
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.COMPARISON,
                    recorded_at="2026-03-28T00:02:00+00:00",
                    status=PlatformReadinessStatus.READY,
                    ready=True,
                    summary="Platform readiness comparison found no dependency state changes.",
                    component_count=2,
                    delta_status=PlatformReadinessDeltaStatus.UNCHANGED,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name="redis_transport",
                            status=PlatformReadinessStatus.READY,
                            ready=True,
                            summary="Redis transport readiness is satisfied.",
                            delta_status=PlatformReadinessDeltaStatus.UNCHANGED,
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_history",
        fake_get_platform_readiness_history,
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history?event_kind=comparison&limit=1",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["total"] == 1
    assert result["items"][0]["event_kind"] == "comparison"


def test_readiness_history_route_supports_component_name_filter(monkeypatch) -> None:
    def fake_get_platform_readiness_history(
        app,
        limit=25,
        recorded_after=None,
        recorded_before=None,
        event_kind=None,
        status=None,
        delta_status=None,
        component_name=None,
        component_delta_status=None,
        component_status=None,
        component_ready=None,
    ) -> PlatformReadinessHistoryResult:
        return PlatformReadinessHistoryResult(
            total=1,
            items=[
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
                    recorded_at="2026-03-28T00:01:00+00:00",
                    status=PlatformReadinessStatus.DEGRADED,
                    ready=False,
                    summary="Platform current readiness is degraded.",
                    component_count=1,
                    delta_status=None,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name=component_name or "database_current",
                            status=PlatformReadinessStatus.DEGRADED,
                            ready=False,
                            summary="Database readiness is degraded.",
                            delta_status=None,
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_history",
        fake_get_platform_readiness_history,
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history?component_name=database",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["total"] == 1
    assert result["items"][0]["components"][0]["name"] == "database"


def test_readiness_history_route_supports_component_delta_status_filter(monkeypatch) -> None:
    def fake_get_platform_readiness_history(
        app,
        limit=25,
        recorded_after=None,
        recorded_before=None,
        event_kind=None,
        status=None,
        delta_status=None,
        component_name=None,
        component_delta_status=None,
        component_status=None,
        component_ready=None,
    ) -> PlatformReadinessHistoryResult:
        return PlatformReadinessHistoryResult(
            total=1,
            items=[
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.COMPARISON,
                    recorded_at="2026-03-28T00:02:00+00:00",
                    status=PlatformReadinessStatus.DEGRADED,
                    ready=False,
                    summary=(
                        "Platform readiness comparison detected dependency regressions "
                        "since startup."
                    ),
                    component_count=1,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name=component_name or "redis_transport",
                            status=PlatformReadinessStatus.DEGRADED,
                            ready=False,
                            summary="Redis transport readiness is degraded.",
                            delta_status=component_delta_status
                            or PlatformReadinessDeltaStatus.REGRESSED,
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_history",
        fake_get_platform_readiness_history,
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history?component_name=redis_transport&component_delta_status=regressed",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["total"] == 1
    assert result["items"][0]["components"][0]["delta_status"] == "regressed"


def test_readiness_history_route_supports_component_status_filter(monkeypatch) -> None:
    def fake_get_platform_readiness_history(
        app,
        limit=25,
        recorded_after=None,
        recorded_before=None,
        event_kind=None,
        status=None,
        delta_status=None,
        component_name=None,
        component_delta_status=None,
        component_status=None,
        component_ready=None,
    ) -> PlatformReadinessHistoryResult:
        return PlatformReadinessHistoryResult(
            total=1,
            items=[
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
                    recorded_at="2026-03-28T00:01:00+00:00",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    summary="Platform current readiness is unavailable.",
                    component_count=1,
                    delta_status=None,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name=component_name or "database_current",
                            status=component_status or PlatformReadinessStatus.UNAVAILABLE,
                            ready=False,
                            summary="Database readiness is unavailable.",
                            delta_status=None,
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_history",
        fake_get_platform_readiness_history,
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history?component_name=database&component_status=unavailable",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["total"] == 1
    assert result["items"][0]["components"][0]["status"] == "unavailable"


def test_readiness_history_route_supports_component_ready_filter(monkeypatch) -> None:
    def fake_get_platform_readiness_history(
        app,
        limit=25,
        recorded_after=None,
        recorded_before=None,
        event_kind=None,
        status=None,
        delta_status=None,
        component_name=None,
        component_delta_status=None,
        component_status=None,
        component_ready=None,
    ) -> PlatformReadinessHistoryResult:
        return PlatformReadinessHistoryResult(
            total=1,
            items=[
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
                    recorded_at="2026-03-28T00:01:00+00:00",
                    status=PlatformReadinessStatus.UNAVAILABLE,
                    ready=False,
                    summary="Platform current readiness is unavailable.",
                    component_count=1,
                    delta_status=None,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name=component_name or "database_current",
                            status=PlatformReadinessStatus.UNAVAILABLE,
                            ready=component_ready if component_ready is not None else False,
                            summary="Database readiness is unavailable.",
                            delta_status=None,
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_history",
        fake_get_platform_readiness_history,
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history?component_name=database&component_ready=false",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["total"] == 1
    assert result["items"][0]["components"][0]["ready"] is False


def test_readiness_history_route_supports_recorded_after_and_before(monkeypatch) -> None:
    def fake_get_platform_readiness_history(
        app,
        limit=25,
        recorded_after=None,
        recorded_before=None,
        event_kind=None,
        status=None,
        delta_status=None,
        component_name=None,
        component_delta_status=None,
        component_status=None,
        component_ready=None,
    ) -> PlatformReadinessHistoryResult:
        assert recorded_after == datetime.fromisoformat("2026-03-28T00:00:30+00:00")
        assert recorded_before == datetime.fromisoformat("2026-03-28T00:02:00+00:00")
        return PlatformReadinessHistoryResult(
            total=1,
            items=[
                PlatformReadinessHistoryEvent(
                    event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
                    recorded_at="2026-03-28T00:01:00+00:00",
                    status=PlatformReadinessStatus.DEGRADED,
                    ready=False,
                    summary="Platform current readiness is degraded.",
                    component_count=1,
                    delta_status=None,
                    components=[
                        PlatformReadinessHistoryComponentSnapshot(
                            name="database_current",
                            status=PlatformReadinessStatus.DEGRADED,
                            ready=False,
                            summary="Database readiness is degraded.",
                            delta_status=None,
                        )
                    ],
                )
            ],
        )

    monkeypatch.setattr(
        runtime_api_module,
        "get_platform_readiness_history",
        fake_get_platform_readiness_history,
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history?recorded_after=2026-03-28T00:00:30%2B00:00&recorded_before=2026-03-28T00:02:00%2B00:00",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["total"] == 1
    assert result["items"][0]["recorded_at"] == "2026-03-28T00:01:00+00:00"


def test_readiness_history_route_rejects_invalid_recorded_after() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/readiness-history?recorded_after=not-a-timestamp",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 422


def test_startup_summary_history_event_includes_component_snapshots() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)

    event = history_service.record_platform_startup_readiness_event(
        history_app,
        PlatformStartupReadinessResult(
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
                    checked_at="2026-03-28T00:00:01+00:00",
                    summary="Database readiness is satisfied.",
                ),
            ],
        ),
    )

    assert [component.name for component in event.components] == [
        "redis_transport_startup",
        "database_startup",
    ]


def test_current_summary_history_event_includes_component_snapshots() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)

    event = history_service.record_platform_current_readiness_event(
        history_app,
        PlatformCurrentReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:01:00+00:00",
            summary="Platform current readiness is degraded.",
            components=[
                PlatformCurrentReadinessComponent(
                    name="redis_transport_current",
                    status=PlatformReadinessStatus.DEGRADED,
                    ready=False,
                    checked_at="2026-03-28T00:01:00+00:00",
                    summary="Redis transport readiness is degraded.",
                )
            ],
        ),
    )

    assert len(event.components) == 1
    assert event.components[0].name == "redis_transport_current"
    assert event.components[0].status == PlatformReadinessStatus.DEGRADED


def test_comparison_history_event_includes_component_snapshots() -> None:
    history_app = FastAPI()
    history_service.initialize_platform_readiness_history(history_app)

    event = history_service.record_platform_readiness_comparison_event(
        history_app,
        PlatformReadinessComparisonResult(
            service_name="sunrise-hes-platform",
            startup_status=PlatformReadinessStatus.READY,
            current_status=PlatformReadinessStatus.UNAVAILABLE,
            delta_status=PlatformReadinessDeltaStatus.REGRESSED,
            ready=False,
            compared_at="2026-03-28T00:02:00+00:00",
            summary="Platform readiness comparison detected dependency regressions since startup.",
            components=[
                PlatformReadinessComparisonComponent(
                    name="redis_transport",
                    startup_status=PlatformReadinessStatus.READY,
                    current_status=PlatformReadinessStatus.UNAVAILABLE,
                    delta_status=PlatformReadinessDeltaStatus.REGRESSED,
                    startup_checked_at="2026-03-28T00:00:00+00:00",
                    current_checked_at="2026-03-28T00:02:00+00:00",
                    startup_summary="Redis transport readiness is satisfied.",
                    current_summary="Redis transport readiness could not reach Redis.",
                )
            ],
        ),
    )

    assert len(event.components) == 1
    assert event.components[0].name == "redis_transport"
    assert event.components[0].delta_status == PlatformReadinessDeltaStatus.REGRESSED
