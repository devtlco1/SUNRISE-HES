from __future__ import annotations

import uuid

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.services import redis_queue_consume as redis_queue_consume_service
from tests.test_scheduler_orchestration_coordinator import (
    _prepare_handled_derived_job_run,
)
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


class UnavailableRedisClient:
    def exists(self, stream_name: str) -> int:
        raise RedisConnectionError("redis unavailable")


def _build_real_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _configure_real_redis_settings(monkeypatch, *, stream_name: str, consumer_group: str) -> None:
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(settings, "redis_queue_stream_name", stream_name)
    monkeypatch.setattr(settings, "redis_queue_consumer_group_name", consumer_group)


def test_redis_dispatch_dequeue_claim_reads_real_stream_message_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
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

    dequeue_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "Runtime Worker A",
            "ensure_consumer_group": True,
        },
    )

    assert dequeue_response.status_code == 200
    result = dequeue_response.json()["result"]
    assert result["status"] == "claimed"
    assert result["stream_name"] == stream_name
    assert result["consumer_group"] == consumer_group
    assert result["consumer_name"] == "hes-worker:runtime-worker-a"
    assert result["dequeue"]["pending_message_id"] == result["message"]["message_id"]
    assert result["claim"]["claim_token"].startswith(
        f"redis-claim:{consumer_group}:hes-worker:runtime-worker-a:"
    )
    assert result["message"]["dispatch_request_identity"] == (
        f"{job_run_id}:retry_dispatch_request"
    )
    assert result["message"]["body"]["source"]["job_run_id"] == job_run_id
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    enqueue_metadata = job_run.result_summary["queue_enqueue"]["enqueue_metadata"]
    assert result["message"]["message_id"] == enqueue_metadata["redis_message_id"]
    assert result["message"]["body"] == enqueue_metadata["serialized_payload"]

    redis_client.delete(stream_name)


def test_redis_dispatch_dequeue_claim_returns_empty_when_no_messages_are_available(
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
    redis_client = _build_real_redis_client()
    redis_client.delete(stream_name)
    redis_client.xadd(stream_name, {"seed": "1"})
    redis_client.xgroup_create(stream_name, consumer_group, id="$", mkstream=False)

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "idle-worker"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "empty"
    assert result["stream_name"] == stream_name
    assert result["consumer_group"] == consumer_group
    assert result["consumer_name"] == "hes-worker:idle-worker"
    assert result["message"] is None
    assert result["dequeue"] is None
    assert result["claim"] is None

    redis_client.delete(stream_name)


def test_redis_dispatch_dequeue_claim_fails_when_redis_is_unavailable(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        redis_queue_consume_service,
        "create_redis_client",
        lambda: UnavailableRedisClient(),
    )

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "unavailable-worker"},
    )

    assert response.status_code == 503
    assert "Redis queue backend is unavailable" in response.json()["detail"]


def test_redis_dispatch_dequeue_claim_fails_when_stream_is_missing(
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
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "missing-stream-worker"},
    )

    assert response.status_code == 404
    assert "Redis dispatch stream does not exist" in response.json()["detail"]


def test_redis_dispatch_dequeue_claim_fails_when_consumer_group_is_missing(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
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

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "nogroup-worker"},
    )

    assert response.status_code == 409
    assert "Redis consumer group is not initialized" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_repeated_redis_dispatch_dequeue_claim_keeps_message_reserved(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
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

    first = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "claiming-worker",
            "ensure_consumer_group": True,
        },
    )
    second = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "claiming-worker"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["result"]["status"] == "claimed"
    assert second.json()["result"]["status"] == "empty"
    assert first.json()["result"]["message"]["dispatch_request_identity"] == (
        f"{job_run_id}:retry_dispatch_request"
    )

    redis_client.delete(stream_name)
