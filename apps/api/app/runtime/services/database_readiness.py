from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import engine
from app.runtime.contracts import (
    DatabaseReadinessDetailResult,
    DatabaseReadinessDetailStatus,
    PlatformReadinessComponent,
    PlatformReadinessStatus,
)


def get_database_readiness_detail() -> DatabaseReadinessDetailResult:
    checked_at = datetime.now(UTC).isoformat()
    database_url = settings.database_url.strip()
    if not database_url:
        return DatabaseReadinessDetailResult(
            status=DatabaseReadinessDetailStatus.DEGRADED,
            ready=False,
            database_url_configured=False,
            database_reachable=False,
            ping_succeeded=False,
            checked_at=checked_at,
            summary="Database readiness is degraded because the database URL is not configured.",
        )

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return DatabaseReadinessDetailResult(
            status=DatabaseReadinessDetailStatus.UNAVAILABLE,
            ready=False,
            database_url_configured=True,
            database_reachable=False,
            ping_succeeded=False,
            checked_at=checked_at,
            summary="Database readiness is unavailable because the database could not be reached.",
        )

    return DatabaseReadinessDetailResult(
        status=DatabaseReadinessDetailStatus.READY,
        ready=True,
        database_url_configured=True,
        database_reachable=True,
        ping_succeeded=True,
        checked_at=checked_at,
        summary="Database readiness is satisfied.",
    )


def evaluate_database_readiness() -> PlatformReadinessComponent:
    detail = get_database_readiness_detail()
    return PlatformReadinessComponent(
        name="database",
        status=_map_database_status(detail.status),
        ready=detail.ready,
        summary=detail.summary,
    )


def _map_database_status(
    detail_status: DatabaseReadinessDetailStatus,
) -> PlatformReadinessStatus:
    if detail_status == DatabaseReadinessDetailStatus.READY:
        return PlatformReadinessStatus.READY
    if detail_status == DatabaseReadinessDetailStatus.UNAVAILABLE:
        return PlatformReadinessStatus.UNAVAILABLE
    return PlatformReadinessStatus.DEGRADED


def get_database_startup_readiness_snapshot(app: FastAPI) -> DatabaseReadinessDetailResult:
    snapshot = getattr(app.state, "database_startup_readiness", None)
    if isinstance(snapshot, DatabaseReadinessDetailResult):
        return snapshot
    return get_database_readiness_detail()
