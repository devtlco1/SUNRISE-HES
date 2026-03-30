from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import main as app_main_module
from app.core.config import settings
from app.main import app
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime import api as runtime_api_module
from app.runtime.contracts import DatabaseReadinessDetailResult
from app.runtime.services import database_readiness as database_readiness_service


class HealthyConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement) -> None:
        del statement


class HealthyEngine:
    def connect(self) -> HealthyConnection:
        return HealthyConnection()


class UnavailableEngine:
    def connect(self):
        raise OperationalError("SELECT 1", {}, Exception("db unavailable"))


def test_database_readiness_reports_ready_when_database_is_reachable(monkeypatch) -> None:
    monkeypatch.setattr(database_readiness_service, "engine", HealthyEngine())

    result = database_readiness_service.evaluate_database_readiness()

    assert result.name == "database"
    assert result.status == "ready"
    assert result.ready is True


def test_database_readiness_detail_reports_ready_when_database_is_reachable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(database_readiness_service, "engine", HealthyEngine())

    result = database_readiness_service.get_database_readiness_detail()

    assert result.status == "ready"
    assert result.ready is True
    assert result.database_url_configured is True
    assert result.database_reachable is True
    assert result.ping_succeeded is True


def test_database_readiness_reports_degraded_when_database_url_is_empty(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "database_url", "   ")

    result = database_readiness_service.evaluate_database_readiness()

    assert result.name == "database"
    assert result.status == "degraded"
    assert result.ready is False


def test_database_readiness_detail_reports_degraded_when_database_url_is_empty(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "database_url", "   ")

    result = database_readiness_service.get_database_readiness_detail()

    assert result.status == "degraded"
    assert result.ready is False
    assert result.database_url_configured is False
    assert result.database_reachable is False
    assert result.ping_succeeded is False


def test_database_readiness_reports_unavailable_when_database_is_unreachable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(database_readiness_service, "engine", UnavailableEngine())

    result = database_readiness_service.evaluate_database_readiness()

    assert result.name == "database"
    assert result.status == "unavailable"
    assert result.ready is False


def test_database_readiness_detail_reports_unavailable_when_database_is_unreachable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(database_readiness_service, "engine", UnavailableEngine())

    result = database_readiness_service.get_database_readiness_detail()

    assert result.status == "unavailable"
    assert result.ready is False
    assert result.database_url_configured is True
    assert result.database_reachable is False
    assert result.ping_succeeded is False


def test_internal_database_readiness_route_reports_detail(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_api_module,
        "get_database_readiness_detail",
        lambda: DatabaseReadinessDetailResult(
            status="ready",
            ready=True,
            database_url_configured=True,
            database_reachable=True,
            ping_succeeded=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Database readiness is satisfied.",
        ),
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/database-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "ready"
    assert result["database_url_configured"] is True
    assert result["database_reachable"] is True
    assert result["ping_succeeded"] is True


def test_database_startup_snapshot_is_persisted_in_app_state(monkeypatch) -> None:
    monkeypatch.setattr(
        app_main_module,
        "get_database_readiness_detail",
        lambda: DatabaseReadinessDetailResult(
            status="ready",
            ready=True,
            database_url_configured=True,
            database_reachable=True,
            ping_succeeded=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Database readiness is satisfied.",
        ),
    )

    with TestClient(app) as client:
        startup_snapshot = client.app.state.database_startup_readiness
        assert startup_snapshot.status == "ready"
        assert startup_snapshot.ready is True
        assert startup_snapshot.database_url_configured is True
        assert startup_snapshot.database_reachable is True
        assert startup_snapshot.ping_succeeded is True


def test_internal_database_startup_readiness_route_reports_startup_snapshot(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_api_module,
        "get_database_startup_readiness_snapshot",
        lambda app: DatabaseReadinessDetailResult(
            status="unavailable",
            ready=False,
            database_url_configured=True,
            database_reachable=False,
            ping_succeeded=False,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Database readiness is unavailable because the database could not be reached.",
        ),
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/internal/platform/database-startup-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "unavailable"
    assert result["ready"] is False
    assert result["database_url_configured"] is True
    assert result["database_reachable"] is False
    assert result["ping_succeeded"] is False


def test_current_database_readiness_route_remains_current_state_oriented(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_api_module,
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
        "get_database_startup_readiness_snapshot",
        lambda app: DatabaseReadinessDetailResult(
            status="unavailable",
            ready=False,
            database_url_configured=True,
            database_reachable=False,
            ping_succeeded=False,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Database readiness is unavailable because the database could not be reached.",
        ),
    )
    client = TestClient(app)

    current_response = client.get(
        "/api/v1/internal/platform/database-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    startup_response = client.get(
        "/api/v1/internal/platform/database-startup-readiness",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert current_response.status_code == 200
    assert startup_response.status_code == 200
    assert current_response.json()["result"]["status"] == "ready"
    assert startup_response.json()["result"]["status"] == "unavailable"
