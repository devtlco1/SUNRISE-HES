from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime.queue_adapters import MockQueueAdapter, queue_adapter_registry
from tests.test_scheduler_orchestration_coordinator import _prepare_handled_derived_job_run
from tests.test_worker_runtime_executor_foundation import _login_as_super_admin


def test_default_adapter_selection_resolves_to_mock_queue_adapter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "queue_backend", "mock")

    adapter = queue_adapter_registry.resolve_configured()

    assert isinstance(adapter, MockQueueAdapter)


def test_configured_adapter_selection_routes_enqueue_through_registry_correctly(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "queue_backend", "mock")
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    assert response.json()["enqueue_result"]["enqueue_metadata"]["adapter"] == "mock_queue_adapter"


def test_unknown_adapter_configuration_fails_cleanly(client, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "queue_backend", "unknown_backend")
    token = _login_as_super_admin(client, db_session)
    job_run_id = _prepare_handled_derived_job_run(client, db_session, token, mode="retry")

    response = client.post(
        f"/api/v1/internal/job-runs/{job_run_id}/enqueue-dispatch-request",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 500
    assert "Unknown queue backend configured" in response.json()["detail"]


def test_list_queue_adapters_endpoint_shows_active_and_available(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "queue_backend", "mock")

    response = client.get(
        "/api/v1/internal/queue/adapters",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_backend"] == "mock"
    items = {item["code"]: item for item in payload["items"]}
    assert {"mock", "redis_placeholder"} <= set(items)
    assert items["mock"]["capabilities"]["supports_receipts"] is True
    assert items["mock"]["capabilities"]["supports_priority"] is False
    assert items["redis_placeholder"]["capabilities"]["supports_visibility_timeout"] is True
