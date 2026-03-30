from __future__ import annotations

import uuid

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.services import redis_queue_recovery as redis_queue_recovery_service
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
            "worker_identifier": "primary-worker",
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


def test_redis_dispatch_pending_inspection_lists_claimed_messages_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, claim_result, stream_name, consumer_group, redis_client = (
        _enqueue_and_claim_message(
            client,
            db_session,
            monkeypatch,
        )
    )

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/pending-inspection",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 0},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["stream_name"] == stream_name
    assert result["consumer_group"] == consumer_group
    assert result["stale_threshold_ms"] == 0
    assert result["total_entries"] == 1
    item = result["items"][0]
    assert item["message_id"] == claim_result["message"]["message_id"]
    assert item["consumer_name"] == "hes-worker:primary-worker"
    assert item["stale"] is True
    assert item["dispatch_request_identity"] == f"{job_run_id}:retry_dispatch_request"

    redis_client.delete(stream_name)


def test_redis_dispatch_recovery_reclaims_a_stale_message_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    job_run_id, claim_result, stream_name, _, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/recover",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "recovery-worker",
            "message_id": claim_result["message"]["message_id"],
            "stale_threshold_ms": 0,
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "reclaimed"
    assert result["stream_name"] == stream_name
    assert result["consumer_name"] == "hes-worker:recovery-worker"
    assert result["original_consumer_name"] == "hes-worker:primary-worker"
    assert result["message_id"] == claim_result["message"]["message_id"]
    assert result["delivery_count"] >= 2
    assert result["recovery_receipt_id"].startswith("redis-recovery:")
    assert result["claim"]["claim_token"].startswith(
        f"redis-claim:{result['consumer_group']}:hes-worker:recovery-worker:"
    )
    assert result["message"]["dispatch_request_identity"] == (
        f"{job_run_id}:retry_dispatch_request"
    )

    ack_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "recovery-worker",
            "message_id": result["message_id"],
            "claim_token": result["claim"]["claim_token"],
        },
    )

    assert ack_response.status_code == 200
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    assert (
        job_run.result_summary["queue_enqueue"]["enqueue_metadata"]["redis_message_id"]
        == result["message_id"]
    )

    redis_client.delete(stream_name)


def test_redis_dispatch_recovery_fails_when_redis_is_unavailable(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        redis_queue_recovery_service,
        "create_redis_client",
        lambda: UnavailableRedisClient(),
    )

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/pending-inspection",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 0},
    )

    assert response.status_code == 503
    assert "Redis queue backend is unavailable" in response.json()["detail"]


def test_redis_dispatch_recovery_fails_when_stream_is_missing(
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
        "/api/v1/internal/queue/dispatch-messages/pending-inspection",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={"stale_threshold_ms": 0},
    )

    assert response.status_code == 404
    assert "Redis dispatch stream does not exist" in response.json()["detail"]


def test_redis_dispatch_recovery_fails_when_consumer_group_is_missing(
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
        "/api/v1/internal/queue/dispatch-messages/recover",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "recovery-worker",
            "message_id": claim_result["message"]["message_id"],
            "stale_threshold_ms": 0,
        },
    )

    assert response.status_code == 409
    assert "Redis consumer group is not initialized" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_redis_dispatch_recovery_fails_when_message_is_not_pending(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    _, claim_result, stream_name, _, redis_client = _enqueue_and_claim_message(
        client,
        db_session,
        monkeypatch,
    )

    ack_response = client.post(
        "/api/v1/internal/queue/dispatch-messages/ack",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "primary-worker",
            "message_id": claim_result["message"]["message_id"],
            "claim_token": claim_result["claim"]["claim_token"],
        },
    )

    assert ack_response.status_code == 200

    response = client.post(
        "/api/v1/internal/queue/dispatch-messages/recover",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "recovery-worker",
            "message_id": claim_result["message"]["message_id"],
            "stale_threshold_ms": 0,
        },
    )

    assert response.status_code == 409
    assert "not currently pending" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_redis_dispatch_recovery_fails_when_message_is_not_stale_enough(
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
        "/api/v1/internal/queue/dispatch-messages/recover",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "recovery-worker",
            "message_id": claim_result["message"]["message_id"],
            "stale_threshold_ms": 60000,
        },
    )

    assert response.status_code == 409
    assert "not stale enough" in response.json()["detail"]

    redis_client.delete(stream_name)


def test_repeated_redis_dispatch_recovery_is_not_allowed_until_message_is_stale_again(
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
        "/api/v1/internal/queue/dispatch-messages/recover",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "recovery-worker",
            "message_id": claim_result["message"]["message_id"],
            "stale_threshold_ms": 0,
        },
    )
    second = client.post(
        "/api/v1/internal/queue/dispatch-messages/recover",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
        json={
            "worker_identifier": "secondary-recovery-worker",
            "message_id": claim_result["message"]["message_id"],
            "stale_threshold_ms": 60000,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "not stale enough" in second.json()["detail"]

    redis_client.delete(stream_name)
