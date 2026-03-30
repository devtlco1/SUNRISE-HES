from __future__ import annotations

import uuid

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime.services import redis_queue_admin as redis_queue_admin_service
from tests.test_scheduler_orchestration_coordinator import (
    _prepare_handled_derived_job_run,
)
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


class UnavailableRedisClient:
    def exists(self, stream_name: str) -> int:
        raise RedisConnectionError("redis unavailable")


def _build_real_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _configure_real_redis_settings(
    monkeypatch,
    *,
    stream_name: str,
    consumer_group: str,
) -> None:
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(settings, "redis_queue_stream_name", stream_name)
    monkeypatch.setattr(settings, "redis_queue_consumer_group_name", consumer_group)


def _enqueue_message(
    client,
    db_session: Session,
    monkeypatch,
) -> tuple[str, str, Redis]:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group = f"hes-worker-group:{uuid.uuid4()}"
    _configure_real_redis_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group=consumer_group,
    )
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    return stream_name, consumer_group, redis_client


def test_redis_transport_admin_bootstraps_consumer_group_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, consumer_group, redis_client = _enqueue_message(
        client,
        db_session,
        monkeypatch,
    )

    response = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["action"] == "bootstrap_consumer_group"
    assert result["status"] == "created"
    assert result["stream_name"] == stream_name
    assert result["consumer_group_name"] == consumer_group
    assert result["consumer_group_exists_before"] is False
    assert result["consumer_group_exists_after"] is True

    redis_client.delete(stream_name)


def test_redis_transport_admin_bootstrap_is_noop_when_group_exists(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, _, redis_client = _enqueue_message(
        client,
        db_session,
        monkeypatch,
    )

    first = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )
    second = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["result"]["status"] == "already_exists"
    assert second.json()["result"]["consumer_group_exists_before"] is True

    redis_client.delete(stream_name)


def test_redis_transport_admin_bootstrap_fails_when_stream_is_missing(
    client,
    monkeypatch,
) -> None:
    stream_name = f"hes:dispatch:test:{uuid.uuid4()}"
    consumer_group = f"hes-worker-group:{uuid.uuid4()}"
    _configure_real_redis_settings(
        monkeypatch,
        stream_name=stream_name,
        consumer_group=consumer_group,
    )
    _build_real_redis_client().delete(stream_name)

    response = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )

    assert response.status_code == 404
    assert "Redis dispatch stream does not exist" in response.json()["detail"]


def test_redis_transport_admin_fails_when_redis_is_unavailable(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        redis_queue_admin_service,
        "create_redis_client",
        lambda: UnavailableRedisClient(),
    )

    response = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )

    assert response.status_code == 503
    assert "Redis queue backend is unavailable" in response.json()["detail"]


def test_redis_transport_admin_refuses_reset_without_explicit_confirmation(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, _, redis_client = _enqueue_message(
        client,
        db_session,
        monkeypatch,
    )
    bootstrap = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )

    assert bootstrap.status_code == 200

    response = client.post(
        "/api/v1/internal/queue/transport-admin/reset-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"confirm_destructive_action": False},
    )

    assert response.status_code == 409
    assert "requires explicit destructive confirmation" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_redis_transport_admin_refuses_reset_when_pending_messages_exist(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, _, redis_client = _enqueue_message(
        client,
        db_session,
        monkeypatch,
    )
    bootstrap = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )
    assert bootstrap.status_code == 200
    claim = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "admin-worker",
        },
    )

    assert claim.status_code == 200

    response = client.post(
        "/api/v1/internal/queue/transport-admin/reset-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"confirm_destructive_action": True},
    )

    assert response.status_code == 409
    assert "pending dispatch messages exist" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_redis_transport_admin_resets_consumer_group_when_safe(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, consumer_group, redis_client = _enqueue_message(
        client,
        db_session,
        monkeypatch,
    )
    bootstrap = client.post(
        "/api/v1/internal/queue/transport-admin/bootstrap-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={},
    )

    assert bootstrap.status_code == 200

    response = client.post(
        "/api/v1/internal/queue/transport-admin/reset-consumer-group",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"confirm_destructive_action": True},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["action"] == "reset_consumer_group"
    assert result["status"] == "reset"
    assert result["stream_name"] == stream_name
    assert result["consumer_group_name"] == consumer_group
    assert result["consumer_group_exists_before"] is True
    assert result["consumer_group_exists_after"] is True
    assert result["pending_count_before"] == 0

    redis_client.delete(stream_name)
