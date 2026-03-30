from __future__ import annotations

from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.jobs.models import JobRun
from app.runtime.queue_adapters import (
    RedisQueueAdapter,
    queue_adapter_registry,
)
from app.runtime.queue_adapters import (
    redis as redis_queue_adapter_module,
)
from tests.test_scheduler_orchestration_coordinator import (
    _prepare_handled_derived_job_run,
)
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


class FakeRedisClient:
    def __init__(self, message_id: str = "1743072000000-0") -> None:
        self.message_id = message_id
        self.calls: list[tuple[str, dict[str, str]]] = []

    def xadd(self, stream_name: str, fields: dict[str, str]) -> str:
        self.calls.append((stream_name, fields))
        return self.message_id


class UnavailableRedisClient:
    def xadd(self, stream_name: str, fields: dict[str, str]) -> str:
        raise RedisConnectionError("redis unavailable")


def test_real_redis_backend_selection_resolves_registered_adapter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "queue_backend", "redis")

    adapter = queue_adapter_registry.resolve_configured()

    assert isinstance(adapter, RedisQueueAdapter)


def test_list_queue_adapters_endpoint_includes_real_redis_backend(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "queue_backend", "redis")

    response = client.get(
        "/api/v1/internal/queue/adapters",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    items = {item["code"]: item for item in payload["items"]}
    assert payload["active_backend"] == "redis"
    assert "redis" in items
    assert items["redis"]["capabilities"]["supports_receipts"] is True
    assert items["redis"]["capabilities"]["supports_visibility_timeout"] is False


def test_real_redis_adapter_publishes_dispatch_payload_successfully(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    fake_client = FakeRedisClient(message_id="1743072000001-0")
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(settings, "redis_queue_stream_name", "hes:dispatch:test")
    monkeypatch.setattr(
        redis_queue_adapter_module,
        "create_redis_client",
        lambda: fake_client,
    )
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()["enqueue_result"]
    assert payload["adapter_receipt_id"] == "redis-receipt:1743072000001-0"
    assert payload["enqueue_metadata"]["adapter"] == "redis_queue_adapter"
    assert payload["enqueue_metadata"]["redis_stream_name"] == "hes:dispatch:test"
    assert payload["enqueue_metadata"]["redis_message_id"] == "1743072000001-0"
    assert payload["enqueue_metadata"]["publish_transport"] == "redis_stream"
    assert (
        payload["enqueue_metadata"]["backend_message_envelope"]["backend_name"]
        == "redis"
    )
    assert len(fake_client.calls) == 1
    stream_name, fields = fake_client.calls[0]
    assert stream_name == "hes:dispatch:test"
    assert fields["dispatch_category"] == "retry_dispatch_request"
    assert fields["dispatch_request_identity"] == f"{job_run_id}:retry_dispatch_request"


def test_real_redis_adapter_failure_surfaces_cleanly(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(
        redis_queue_adapter_module,
        "create_redis_client",
        lambda: UnavailableRedisClient(),
    )
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 503
    assert "Redis queue backend is unavailable" in response.json()["detail"]


def test_repeated_enqueue_calls_publish_once_with_real_redis_backend(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    fake_client = FakeRedisClient(message_id="1743072000002-0")
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(
        redis_queue_adapter_module,
        "create_redis_client",
        lambda: fake_client,
    )
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    first = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    second = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["enqueue_result"] == second.json()["enqueue_result"]
    assert len(fake_client.calls) == 1


def test_real_redis_enqueue_summary_persists_in_job_run_projection(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    fake_client = FakeRedisClient(message_id="1743072000003-0")
    monkeypatch.setattr(settings, "queue_backend", "redis")
    monkeypatch.setattr(
        redis_queue_adapter_module,
        "create_redis_client",
        lambda: fake_client,
    )
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    job_run = db_session.get(JobRun, job_run_id)
    assert job_run is not None
    enqueue_metadata = job_run.result_summary["queue_enqueue"]["enqueue_metadata"]
    assert enqueue_metadata["adapter"] == "redis_queue_adapter"
    assert enqueue_metadata["redis_message_id"] == "1743072000003-0"
    assert enqueue_metadata["backend_message_envelope"]["envelope_body"]["stream"] == (
        "hes:dispatch"
    )
