from __future__ import annotations

import uuid

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime.services import redis_queue_status as redis_queue_status_service
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


def _enqueue_and_optionally_claim_message(
    client,
    db_session: Session,
    monkeypatch,
    *,
    claim_message: bool,
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

    enqueue_response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert enqueue_response.status_code == 200

    if claim_message:
        claim_response = client.post(
            "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
            json={
                "worker_identifier": "status-worker",
                "ensure_consumer_group": True,
            },
        )
        assert claim_response.status_code == 200

    return stream_name, consumer_group, redis_client


def test_redis_transport_status_reports_healthy_stream_and_group(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, consumer_group, redis_client = _enqueue_and_optionally_claim_message(
        client,
        db_session,
        monkeypatch,
        claim_message=True,
    )

    response = client.post(
        "/api/v1/internal/queue/transport-status",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 60000},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "ready"
    assert result["ready"] is True
    assert result["stream_name"] == stream_name
    assert result["stream_exists"] is True
    assert result["stream_depth"] >= 1
    assert result["consumer_group_name"] == consumer_group
    assert result["consumer_group_exists"] is True
    assert result["consumer_count"] >= 1
    assert result["pending_count"] >= 1
    assert result["stale_pending_count"] == 0

    redis_client.delete(stream_name)


def test_redis_transport_status_reports_missing_stream_cleanly(
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
        "/api/v1/internal/queue/transport-status",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 0},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "degraded"
    assert result["ready"] is False
    assert result["stream_exists"] is False
    assert result["consumer_group_exists"] is False
    assert result["stream_depth"] == 0


def test_redis_transport_status_reports_missing_group_cleanly(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, _, redis_client = _enqueue_and_optionally_claim_message(
        client,
        db_session,
        monkeypatch,
        claim_message=False,
    )

    response = client.post(
        "/api/v1/internal/queue/transport-status",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 0},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "degraded"
    assert result["ready"] is False
    assert result["stream_exists"] is True
    assert result["consumer_group_exists"] is False
    assert result["stream_depth"] >= 1

    redis_client.delete(stream_name)


def test_redis_transport_status_reports_pending_entries(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, _, redis_client = _enqueue_and_optionally_claim_message(
        client,
        db_session,
        monkeypatch,
        claim_message=True,
    )

    response = client.post(
        "/api/v1/internal/queue/transport-status",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 60000},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["pending_count"] >= 1
    assert result["inspected_pending_count"] >= 1
    assert result["oldest_pending_idle_ms"] is not None

    redis_client.delete(stream_name)


def test_redis_transport_status_reports_stale_pending_entries(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    stream_name, _, redis_client = _enqueue_and_optionally_claim_message(
        client,
        db_session,
        monkeypatch,
        claim_message=True,
    )

    response = client.post(
        "/api/v1/internal/queue/transport-status",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 0},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "degraded"
    assert result["ready"] is False
    assert result["stale_pending_count"] >= 1
    assert result["oldest_pending_idle_ms"] is not None

    redis_client.delete(stream_name)


def test_redis_transport_status_fails_when_redis_is_unavailable(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        redis_queue_status_service,
        "create_redis_client",
        lambda: UnavailableRedisClient(),
    )

    response = client.post(
        "/api/v1/internal/queue/transport-status",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 0},
    )

    assert response.status_code == 503
    assert "Redis queue backend is unavailable" in response.json()["detail"]
