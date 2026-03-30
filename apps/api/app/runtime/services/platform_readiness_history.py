from __future__ import annotations

from collections import deque
from datetime import datetime

from fastapi import FastAPI

from app.runtime.contracts import (
    PlatformCurrentReadinessResult,
    PlatformReadinessComparisonResult,
    PlatformReadinessDeltaStatus,
    PlatformReadinessHistoryComponentSnapshot,
    PlatformReadinessHistoryEvent,
    PlatformReadinessHistoryEventKind,
    PlatformReadinessHistoryResult,
    PlatformReadinessStatus,
    PlatformStartupReadinessResult,
)

READINESS_HISTORY_MAX_EVENTS = 25


def initialize_platform_readiness_history(app: FastAPI) -> None:
    if not hasattr(app.state, "platform_readiness_history"):
        app.state.platform_readiness_history = deque(maxlen=READINESS_HISTORY_MAX_EVENTS)


def record_platform_startup_readiness_event(
    app: FastAPI,
    result: PlatformStartupReadinessResult,
) -> PlatformReadinessHistoryEvent:
    return _record_event(
        app=app,
        event=PlatformReadinessHistoryEvent(
            event_kind=PlatformReadinessHistoryEventKind.STARTUP_SUMMARY,
            recorded_at=result.checked_at,
            status=result.status,
            ready=result.ready,
            summary=result.summary,
            component_count=len(result.components),
            components=[
                PlatformReadinessHistoryComponentSnapshot(
                    name=component.name,
                    status=component.status,
                    ready=component.ready,
                    summary=component.summary,
                )
                for component in result.components
            ],
        ),
    )


def record_platform_current_readiness_event(
    app: FastAPI,
    result: PlatformCurrentReadinessResult,
) -> PlatformReadinessHistoryEvent:
    return _record_event(
        app=app,
        event=PlatformReadinessHistoryEvent(
            event_kind=PlatformReadinessHistoryEventKind.CURRENT_SUMMARY,
            recorded_at=result.checked_at,
            status=result.status,
            ready=result.ready,
            summary=result.summary,
            component_count=len(result.components),
            components=[
                PlatformReadinessHistoryComponentSnapshot(
                    name=component.name,
                    status=component.status,
                    ready=component.ready,
                    summary=component.summary,
                )
                for component in result.components
            ],
        ),
    )


def record_platform_readiness_comparison_event(
    app: FastAPI,
    result: PlatformReadinessComparisonResult,
) -> PlatformReadinessHistoryEvent:
    return _record_event(
        app=app,
        event=PlatformReadinessHistoryEvent(
            event_kind=PlatformReadinessHistoryEventKind.COMPARISON,
            recorded_at=result.compared_at,
            status=result.current_status,
            ready=result.ready,
            summary=result.summary,
            component_count=len(result.components),
            delta_status=result.delta_status,
            components=[
                PlatformReadinessHistoryComponentSnapshot(
                    name=component.name,
                    status=component.current_status,
                    ready=component.current_status == PlatformReadinessStatus.READY,
                    summary=component.current_summary,
                    delta_status=component.delta_status,
                )
                for component in result.components
            ],
        ),
    )


def get_platform_readiness_history(
    app: FastAPI,
    *,
    limit: int = READINESS_HISTORY_MAX_EVENTS,
    recorded_after: datetime | None = None,
    recorded_before: datetime | None = None,
    event_kind: PlatformReadinessHistoryEventKind | None = None,
    status: PlatformReadinessStatus | None = None,
    delta_status: PlatformReadinessDeltaStatus | None = None,
    component_name: str | None = None,
    component_delta_status: PlatformReadinessDeltaStatus | None = None,
    component_status: PlatformReadinessStatus | None = None,
    component_ready: bool | None = None,
) -> PlatformReadinessHistoryResult:
    initialize_platform_readiness_history(app)
    items = list(app.state.platform_readiness_history)
    if recorded_after is not None:
        items = [item for item in items if _parse_recorded_at(item.recorded_at) >= recorded_after]
    if recorded_before is not None:
        items = [item for item in items if _parse_recorded_at(item.recorded_at) <= recorded_before]
    if event_kind is not None:
        items = [item for item in items if item.event_kind == event_kind]
    if status is not None:
        items = [item for item in items if item.status == status]
    if delta_status is not None:
        items = [
            item
            for item in items
            if item.delta_status is not None and item.delta_status == delta_status
        ]
    if component_name is not None:
        items = [
            item
            for item in items
            if any(
                _component_matches(
                    component=component,
                    component_name=component_name,
                )
                for component in item.components
            )
        ]
    if component_delta_status is not None:
        if component_name is None:
            items = []
        else:
            items = [
                item
                for item in items
                if any(
                    _component_matches(
                        component=component,
                        component_name=component_name,
                        component_delta_status=component_delta_status,
                    )
                    for component in item.components
                )
            ]
    if component_status is not None:
        if component_name is None:
            items = []
        else:
            items = [
                item
                for item in items
                if any(
                    _component_matches(
                        component=component,
                        component_name=component_name,
                        component_status=component_status,
                    )
                    for component in item.components
                )
            ]
    if component_ready is not None:
        if component_name is None:
            items = []
        else:
            items = [
                item
                for item in items
                if any(
                    _component_matches(
                        component=component,
                        component_name=component_name,
                        component_ready=component_ready,
                    )
                    for component in item.components
                )
            ]
    items = items[:limit]
    return PlatformReadinessHistoryResult(total=len(items), items=items)


def _record_event(
    *,
    app: FastAPI,
    event: PlatformReadinessHistoryEvent,
) -> PlatformReadinessHistoryEvent:
    initialize_platform_readiness_history(app)
    app.state.platform_readiness_history.appendleft(event)
    return event


def _component_matches(
    *,
    component: PlatformReadinessHistoryComponentSnapshot,
    component_name: str,
    component_delta_status: PlatformReadinessDeltaStatus | None = None,
    component_status: PlatformReadinessStatus | None = None,
    component_ready: bool | None = None,
) -> bool:
    normalized_snapshot_name = _normalize_component_name(component.name)
    normalized_requested_name = _normalize_component_name(component_name)
    name_matches = (
        component.name == component_name
        or normalized_snapshot_name == component_name
        or component.name == normalized_requested_name
        or normalized_snapshot_name == normalized_requested_name
    )
    if not name_matches:
        return False
    if component_delta_status is None:
        delta_matches = True
    else:
        delta_matches = (
            component.delta_status is not None and component.delta_status == component_delta_status
        )
    if not delta_matches:
        return False
    if component_status is None:
        status_matches = True
    else:
        status_matches = component.status == component_status
    if not status_matches:
        return False
    if component_ready is None:
        return True
    return component.ready == component_ready


def _normalize_component_name(name: str) -> str:
    for suffix in ("_startup", "_current"):
        if name.endswith(suffix):
            return name.removesuffix(suffix)
    return name


def _parse_recorded_at(recorded_at: str) -> datetime:
    return datetime.fromisoformat(recorded_at)
