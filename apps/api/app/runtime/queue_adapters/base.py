from __future__ import annotations

from typing import Protocol

from app.runtime.contracts import QueueEnqueuePayload, QueueEnqueueResult


class BaseQueueAdapter(Protocol):
    def enqueue(self, payload: QueueEnqueuePayload) -> QueueEnqueueResult:
        ...
