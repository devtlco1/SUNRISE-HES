from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI

from app.core.config import settings
from app.runtime.contracts import (
    PlatformReadinessComparisonComponent,
    PlatformReadinessComparisonResult,
    PlatformReadinessDeltaStatus,
    PlatformReadinessStatus,
)
from app.runtime.services.platform_current_readiness import get_platform_current_readiness
from app.runtime.services.platform_startup_readiness import get_platform_startup_readiness


def get_platform_readiness_comparison(app: FastAPI) -> PlatformReadinessComparisonResult:
    startup = get_platform_startup_readiness(app)
    current = get_platform_current_readiness()
    startup_components = {
        _normalize_component_name(component.name): component for component in startup.components
    }
    current_components = {
        _normalize_component_name(component.name): component for component in current.components
    }
    component_names = sorted(set(startup_components) | set(current_components))
    components = [
        _build_component_comparison(
            name=name,
            startup_component=startup_components[name],
            current_component=current_components[name],
        )
        for name in component_names
    ]
    delta_status = _summarize_delta_status(components)
    return PlatformReadinessComparisonResult(
        service_name=settings.project_name,
        startup_status=startup.status,
        current_status=current.status,
        delta_status=delta_status,
        ready=current.ready,
        compared_at=datetime.now(UTC).isoformat(),
        summary=_build_comparison_summary(delta_status=delta_status),
        components=components,
    )


def _build_component_comparison(
    *,
    name: str,
    startup_component,
    current_component,
) -> PlatformReadinessComparisonComponent:
    return PlatformReadinessComparisonComponent(
        name=name,
        startup_status=startup_component.status,
        current_status=current_component.status,
        delta_status=_classify_delta(
            startup_status=startup_component.status,
            current_status=current_component.status,
        ),
        startup_checked_at=startup_component.checked_at,
        current_checked_at=current_component.checked_at,
        startup_summary=startup_component.summary,
        current_summary=current_component.summary,
    )


def _normalize_component_name(name: str) -> str:
    if name.endswith("_startup"):
        return name.removesuffix("_startup")
    if name.endswith("_current"):
        return name.removesuffix("_current")
    return name


def _classify_delta(
    *,
    startup_status: PlatformReadinessStatus,
    current_status: PlatformReadinessStatus,
) -> PlatformReadinessDeltaStatus:
    if startup_status == current_status:
        return PlatformReadinessDeltaStatus.UNCHANGED
    if startup_status == PlatformReadinessStatus.READY:
        return PlatformReadinessDeltaStatus.REGRESSED
    if current_status == PlatformReadinessStatus.READY:
        return PlatformReadinessDeltaStatus.RECOVERED
    return PlatformReadinessDeltaStatus.CHANGED


def _summarize_delta_status(
    components: list[PlatformReadinessComparisonComponent],
) -> PlatformReadinessDeltaStatus:
    if any(
        component.delta_status == PlatformReadinessDeltaStatus.REGRESSED for component in components
    ):
        return PlatformReadinessDeltaStatus.REGRESSED
    if any(
        component.delta_status == PlatformReadinessDeltaStatus.RECOVERED for component in components
    ):
        return PlatformReadinessDeltaStatus.RECOVERED
    if any(
        component.delta_status == PlatformReadinessDeltaStatus.CHANGED for component in components
    ):
        return PlatformReadinessDeltaStatus.CHANGED
    return PlatformReadinessDeltaStatus.UNCHANGED


def _build_comparison_summary(
    *,
    delta_status: PlatformReadinessDeltaStatus,
) -> str:
    if delta_status == PlatformReadinessDeltaStatus.UNCHANGED:
        return "Platform readiness comparison found no dependency state changes."
    if delta_status == PlatformReadinessDeltaStatus.REGRESSED:
        return "Platform readiness comparison detected dependency regressions since startup."
    if delta_status == PlatformReadinessDeltaStatus.RECOVERED:
        return "Platform readiness comparison detected dependency recovery since startup."
    return "Platform readiness comparison detected dependency state changes."
