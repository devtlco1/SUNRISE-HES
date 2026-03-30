from fastapi.testclient import TestClient

from app.api.v1.routes import health as health_route_module
from app.main import app
from app.runtime.contracts import (
    PlatformReadinessResult,
    PlatformReadinessStatus,
)


def test_healthcheck() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/platform/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_platform_readiness_reports_ready_when_redis_transport_is_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        health_route_module,
        "get_platform_readiness",
        lambda: PlatformReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform readiness is satisfied.",
            components=[],
        ),
    )
    client = TestClient(app)

    response = client.get("/api/v1/platform/readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["ready"] is True


def test_platform_readiness_reports_degraded_when_dependency_is_not_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        health_route_module,
        "get_platform_readiness",
        lambda: PlatformReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.DEGRADED,
            ready=False,
            checked_at="2026-03-28T00:00:00+00:00",
            summary=(
                "Platform readiness is degraded because a required dependency is not fully ready."
            ),
            components=[],
        ),
    )
    client = TestClient(app)

    response = client.get("/api/v1/platform/readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ready"] is False


def test_platform_readiness_route_is_simpler_than_internal_transport_readiness(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        health_route_module,
        "get_platform_readiness",
        lambda: PlatformReadinessResult(
            service_name="sunrise-hes-platform",
            status=PlatformReadinessStatus.READY,
            ready=True,
            checked_at="2026-03-28T00:00:00+00:00",
            summary="Platform readiness is satisfied.",
            components=[
                {
                    "name": "redis_transport",
                    "status": "ready",
                    "ready": True,
                    "summary": "Redis transport readiness is satisfied.",
                },
                {
                    "name": "database",
                    "status": "ready",
                    "ready": True,
                    "summary": "Database readiness is satisfied.",
                },
            ],
        ),
    )
    client = TestClient(app)

    public_response = client.get("/api/v1/platform/readiness")

    assert public_response.status_code == 200
    public_result = public_response.json()
    assert "service_name" in public_result
    assert "components" in public_result
    assert [component["name"] for component in public_result["components"]] == [
        "redis_transport",
        "database",
    ]
    assert "stream_name" not in public_result
    assert "consumer_group_name" not in public_result
    assert "database_url_configured" not in public_result
    assert "database_reachable" not in public_result
    assert "ping_succeeded" not in public_result
