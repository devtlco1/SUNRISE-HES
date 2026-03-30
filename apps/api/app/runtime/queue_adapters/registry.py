from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.core.config import settings
from app.runtime.contracts import QueueAdapterCapabilities
from app.runtime.queue_adapters.base import BaseQueueAdapter
from app.runtime.queue_adapters.mock import MockQueueAdapter
from app.runtime.queue_adapters.redis import RedisQueueAdapter
from app.runtime.queue_adapters.redis_placeholder import RedisPlaceholderQueueAdapter


@dataclass(frozen=True)
class QueueAdapterDescriptor:
    code: str
    implementation: str
    capabilities: QueueAdapterCapabilities
    is_default: bool = False


class QueueAdapterRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, type[BaseQueueAdapter]] = {}
        self._capabilities: dict[str, QueueAdapterCapabilities] = {}

    def register(
        self,
        code: str,
        adapter_cls: type[BaseQueueAdapter],
        *,
        capabilities: QueueAdapterCapabilities,
    ) -> None:
        self._factories[code] = adapter_cls
        self._capabilities[code] = capabilities

    def resolve(self, code: str) -> BaseQueueAdapter:
        adapter_cls = self._factories.get(code)
        if adapter_cls is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unknown queue backend configured: '{code}'.",
            )
        return adapter_cls()

    def resolve_configured(self) -> BaseQueueAdapter:
        return self.resolve(settings.queue_backend)

    def list_descriptors(self) -> list[QueueAdapterDescriptor]:
        return [
            QueueAdapterDescriptor(
                code=code,
                implementation=adapter_cls.__name__,
                capabilities=self._capabilities[code],
                is_default=code == "mock",
            )
            for code, adapter_cls in sorted(self._factories.items())
        ]


queue_adapter_registry = QueueAdapterRegistry()
queue_adapter_registry.register(
    "mock",
    MockQueueAdapter,
    capabilities=QueueAdapterCapabilities(
        supports_priority=False,
        supports_delay=False,
        supports_receipts=True,
        supports_deduplication=False,
        supports_visibility_timeout=False,
    ),
)
queue_adapter_registry.register(
    "redis",
    RedisQueueAdapter,
    capabilities=QueueAdapterCapabilities(
        supports_priority=False,
        supports_delay=False,
        supports_receipts=True,
        supports_deduplication=False,
        supports_visibility_timeout=False,
    ),
)
queue_adapter_registry.register(
    "redis_placeholder",
    RedisPlaceholderQueueAdapter,
    capabilities=QueueAdapterCapabilities(
        supports_priority=True,
        supports_delay=True,
        supports_receipts=True,
        supports_deduplication=True,
        supports_visibility_timeout=True,
    ),
)
