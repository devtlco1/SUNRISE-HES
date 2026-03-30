from __future__ import annotations

from app.core.config import settings
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER


def test_redis_transport_config_reports_effective_defaults(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "redis_queue_stream_name", "hes:dispatch")
    monkeypatch.setattr(settings, "redis_queue_consumer_group_name", "hes-worker-group")
    monkeypatch.setattr(settings, "redis_queue_claim_timeout_seconds", 300)
    monkeypatch.setattr(settings, "redis_queue_stale_claim_threshold_seconds", 300)
    monkeypatch.setattr(settings, "redis_queue_dead_letter_stream_name", None)
    monkeypatch.setattr(settings, "redis_queue_validate_on_startup", False)
    monkeypatch.setattr(settings, "redis_queue_ensure_stream_on_startup", False)
    monkeypatch.setattr(settings, "redis_queue_ensure_consumer_group_on_startup", False)

    response = client.get(
        "/api/v1/internal/queue/transport-config",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["stream_name"] == "hes:dispatch"
    assert result["consumer_group_name"] == "hes-worker-group"
    assert result["claim_timeout_seconds"] == 300
    assert result["stale_claim_threshold_seconds"] == 300
    assert result["dead_letter_stream_name"] == "hes:dispatch:dead-letter"
    assert result["validate_on_startup"] is False
    assert result["ensure_stream_on_startup"] is False
    assert result["ensure_consumer_group_on_startup"] is False


def test_redis_transport_config_reports_custom_dead_letter_override(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "redis_queue_stream_name", "hes:dispatch:prod")
    monkeypatch.setattr(settings, "redis_queue_consumer_group_name", "hes-worker-group-prod")
    monkeypatch.setattr(settings, "redis_queue_claim_timeout_seconds", 180)
    monkeypatch.setattr(settings, "redis_queue_stale_claim_threshold_seconds", 600)
    monkeypatch.setattr(settings, "redis_queue_validate_on_startup", True)
    monkeypatch.setattr(settings, "redis_queue_ensure_stream_on_startup", True)
    monkeypatch.setattr(settings, "redis_queue_ensure_consumer_group_on_startup", True)
    monkeypatch.setattr(
        settings,
        "redis_queue_dead_letter_stream_name",
        "hes:dispatch:prod:dlq",
    )

    response = client.get(
        "/api/v1/internal/queue/transport-config",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["stream_name"] == "hes:dispatch:prod"
    assert result["consumer_group_name"] == "hes-worker-group-prod"
    assert result["claim_timeout_seconds"] == 180
    assert result["stale_claim_threshold_seconds"] == 600
    assert result["dead_letter_stream_name"] == "hes:dispatch:prod:dlq"
    assert result["validate_on_startup"] is True
    assert result["ensure_stream_on_startup"] is True
    assert result["ensure_consumer_group_on_startup"] is True


def test_redis_transport_config_route_remains_compatible_with_queue_listing(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "queue_backend", "redis")

    config_response = client.get(
        "/api/v1/internal/queue/transport-config",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )
    adapters_response = client.get(
        "/api/v1/internal/queue/adapters",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert config_response.status_code == 200
    assert adapters_response.status_code == 200
    assert adapters_response.json()["active_backend"] == "redis"
