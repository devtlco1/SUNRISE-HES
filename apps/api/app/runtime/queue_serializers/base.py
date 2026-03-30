from __future__ import annotations

from typing import Protocol

from app.runtime.contracts import QueueBackendMessageEnvelope, QueueEnqueuePayload


class BaseQueueMessageSerializer(Protocol):
    def serialize(self, payload: QueueEnqueuePayload) -> QueueBackendMessageEnvelope:
        ...
