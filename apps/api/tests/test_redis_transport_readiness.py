from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import settings
from app.main import app
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime.services import redis_queue_readiness as redis_queue_readiness_service


class UnavailableRedisClient:
    def exists(self, stream_name: str) -> int:
        raise RedisConnectionError("redis unavailable")


def _build_real_redis_client() -> Redis:
    return Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)


def _configure_startup_settings(
    monkeypatch,
    *,
    stream_name: str,
    consumer_group_name: str,
    validate_on_startup: bool,
    ensure_stream_on_startup: bool,
    ensure_consumer_group_on_startup: bool,
) -> None:
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "redis_queue_stream_name", stream_name)
    monkeypatch.setattr(settings, "redis_queue_consumer_group_name", consumer_group_name)
    monkeypatch.setattr(settings, "redis_queue_validate_on_startup", validate_on_startup)
    monkeypatch.setattr(
        settings,
        "redis_queue_ensure_stream_on_startup",
        ensure_stream_on_startup,
    )
    monkeypatch.setattr(
        settings,
        "redis_queue_ensure_consumer_group_on_startup",
        ensure_consumer_group_on_startup,
    )


def test_redis_transport_readiness_reports_ready_when_stream_and_group_are_healthy(
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group_name = f"hes-worker-group:{uuid.uuid4()}"
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    redis_client.xadd(stream_name, {"seed": "1"})
    redis_client.xgroup_create(stream_name, consumer_group_name, id="0", mkstream=False)
    _configure_startup_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
        validate_on_startup=False,
        ensure_stream_on_startup=False,
        ensure_consumer_group_on_startup=False,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/internal/queue/transport-readiness",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        )

        assert response.status_code == 200
        result = response.json()["result"]
        assert result["status"] == "ready"
        assert result["ready"] is True
        assert result["redis_reachable"] is True
        assert result["stream_ready"] is True
        assert result["consumer_group_ready"] is True

    redis_client.delete(stream_name)


def test_redis_transport_readiness_reports_unavailable_when_redis_is_unreachable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        redis_queue_readiness_service,
        "create_redis_client",
        lambda: UnavailableRedisClient(),
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/internal/queue/transport-readiness",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        )

        assert response.status_code == 200
        result = response.json()["result"]
        assert result["status"] == "unavailable"
        assert result["ready"] is False
        assert result["redis_reachable"] is False


def test_redis_transport_startup_snapshot_is_skipped_when_validation_is_disabled(
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group_name = f"hes-worker-group:{uuid.uuid4()}"
    _configure_startup_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
        validate_on_startup=False,
        ensure_stream_on_startup=False,
        ensure_consumer_group_on_startup=False,
    )

    with TestClient(app) as client:
        startup_snapshot = client.app.state.redis_transport_startup_readiness
        assert startup_snapshot.validation_performed is False
        assert startup_snapshot.status == "degraded"
        assert startup_snapshot.summary == "Redis transport startup validation is disabled."


def test_redis_transport_startup_can_ensure_stream_and_group_when_enabled(
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group_name = f"hes-worker-group:{uuid.uuid4()}"
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    _configure_startup_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
        validate_on_startup=True,
        ensure_stream_on_startup=True,
        ensure_consumer_group_on_startup=True,
    )

    with TestClient(app) as client:
        startup_snapshot = client.app.state.redis_transport_startup_readiness
        assert startup_snapshot.validation_performed is True
        assert startup_snapshot.bootstrap_applied is True
        assert startup_snapshot.status == "ready"
        assert startup_snapshot.ready is True
        assert startup_snapshot.stream_ready is True
        assert startup_snapshot.consumer_group_ready is True

    groups = redis_client.xinfo_groups(stream_name)
    assert any(str(group.get("name")) == consumer_group_name for group in groups)
    redis_client.delete(stream_name)


def test_redis_transport_readiness_route_is_compatible_with_existing_transport_config(
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group_name = f"hes-worker-group:{uuid.uuid4()}"
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    redis_client.xadd(stream_name, {"seed": "1"})
    redis_client.xgroup_create(stream_name, consumer_group_name, id="0", mkstream=False)
    _configure_startup_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group_name=consumer_group_name,
        validate_on_startup=True,
        ensure_stream_on_startup=False,
        ensure_consumer_group_on_startup=False,
    )

    with TestClient(app) as client:
        readiness_response = client.get(
            "/api/v1/internal/queue/transport-readiness",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        )
        config_response = client.get(
            "/api/v1/internal/queue/transport-config",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        )

        assert readiness_response.status_code == 200
        assert config_response.status_code == 200
        assert (
            readiness_response.json()["result"]["stream_name"]
            == config_response.json()["result"]["stream_name"]
        )
        assert (
            readiness_response.json()["result"]["consumer_group_name"]
            == config_response.json()["result"]["consumer_group_name"]
        )

    redis_client.delete(stream_name)
