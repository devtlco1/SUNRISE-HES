from __future__ import annotations

import uuid

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.services import redis_queue_completion as redis_queue_completion_service
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


def _enqueue_and_claim_message(
    client,
    db_session: Session,
    monkeypatch,
) -> tuple[str, dict[str, object], str, str, Redis]:
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

    claim_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "ensure_consumer_group": True,
        },
    )

    assert claim_response.status_code == 200
    return (
        job_run_id,
        claim_response.json()["result"],
        stream_name,
        consumer_group,
        redis_client,
    )


def test_redis_dispatch_ack_acknowledges_a_claimed_message_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, claim_result, stream_name, _, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )

    ack_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert ack_response.status_code == 200
    result = ack_response.json()["result"]
    assert result["status"] == "acked"
    assert result["stream_name"] == stream_name
    assert result["consumer_name"] == "hes-worker:ack-worker"
    assert result["message_id"] == claim_result["message"]["message_id"]
    assert result["ack_receipt_id"].startswith("redis-ack:")
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    assert (
        job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["redis_message_id"]
        == claim_result["message"]["message_id"]
    )

    redis_client.delete(stream_name)


def test_redis_dispatch_release_requeues_a_claimed_message_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, claim_result, stream_name, _, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )

    release_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/release",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
            "reason": "worker-retry",
        },
    )

    assert release_response.status_code == 200
    result = release_response.json()["result"]
    assert result["status"] == "released"
    assert result["release_mode"] == "requeued_copy"
    assert result["stream_name"] == stream_name
    assert result["original_message_id"] == claim_result["message"]["message_id"]
    assert result["requeued_message_id"] != claim_result["message"]["message_id"]
    assert result["release_receipt_id"].startswith("redis-release:")

    dequeue_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/dequeue-claim",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"worker_identifier": "ack-worker"},
    )

    assert dequeue_response.status_code == 200
    requeued_result = dequeue_response.json()["result"]
    assert requeued_result["status"] == "claimed"
    assert requeued_result["message"]["message_id"] == result["requeued_message_id"]
    assert requeued_result["message"]["dispatch_request_identity"] == (
        f"{job_run_id}:retry_dispatch_request"
    )
    assert (
        requeued_result["message"]["body"]["source"]["job_run_id"]
        == claim_result["message"]["body"]["source"]["job_run_id"]
    )

    redis_client.delete(stream_name)


def test_redis_dispatch_ack_fails_when_redis_is_unavailable(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        redis_queue_completion_service,
        "create_redis_client",
        lambda: UnavailableRedisClient(),
    )

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": "0-1",
            "claim_token": "redis-claim:test:hes-worker:ack-worker:0-1:123",
        },
    )

    assert response.status_code == 503
    assert "Redis queue backend is unavailable" in response.json()["detail"]


def test_redis_dispatch_ack_fails_when_message_does_not_exist(
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
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": "999999-0",
            "claim_token": "redis-claim:test:hes-worker:ack-worker:999999-0:123",
        },
    )

    assert response.status_code == 404
    assert "Redis dispatch message does not exist" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_redis_dispatch_ack_fails_when_stream_is_missing(
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
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": "123-0",
            "claim_token": "redis-claim:test:hes-worker:ack-worker:123-0:123",
        },
    )

    assert response.status_code == 404
    assert "Redis dispatch stream does not exist" in response.json()["detail"]


def test_redis_dispatch_release_fails_when_consumer_group_is_missing(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, claim_result, stream_name, consumer_group, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )
    redis_client.xgroup_destroy(stream_name, consumer_group)

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/release",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert response.status_code == 409
    assert "Redis consumer group is not initialized" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_redis_dispatch_release_fails_when_claim_state_is_invalid(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, claim_result, stream_name, _, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/release",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "different-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert response.status_code == 409
    assert "Claim token is invalid" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_repeated_redis_dispatch_ack_returns_invalid_claim_state_after_completion(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, claim_result, stream_name, _, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )

    first = client.post(
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )
    second = client.post(
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "valid pending state" in second.json()["detail"]

    redis_client.delete(stream_name)


def test_repeated_redis_dispatch_release_returns_invalid_claim_state_after_completion(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, claim_result, stream_name, _, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )

    first = client.post(
        "/api/v1/internal/queue/dispatch-messages/release",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )
    second = client.post(
        "/api/v1/internal/queue/dispatch-messages/release",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "ack-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "valid pending state" in second.json()["detail"]

    redis_client.delete(stream_name)
