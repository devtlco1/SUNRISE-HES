from __future__ import annotations

from pydantic import BaseModel


class RuntimeExecutionGuardResult(BaseModel):
    guard_record_id: str
    executor_identifier: str
    attempt_id: str
    lease_record_id: str
    invocation_record_id: str
    execution_started_at: str
    guard_expires_at: str
    dispatch_request_identity: str
    queue_message_id: str
    claim_token: str

    def get(self, key: str, default: object | None = None) -> object | None:
        return getattr(self, key, default)
