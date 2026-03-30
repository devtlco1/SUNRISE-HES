from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerReconciliationSnapshot(StringEnum):
    RECONCILIATION_SNAPSHOT = "reconciliation_snapshot"
    QUEUE_HEALTH_SNAPSHOT = "queue_health_snapshot"
    CLOSURE_DRIFT_SNAPSHOT = "closure_drift_snapshot"
    AUDIT_READY_SNAPSHOT = "audit_ready_snapshot"
    NOOP_RECONCILIATION_SNAPSHOT = "noop_reconciliation_snapshot"


class RedisWorkerReconciliationRecord(BaseModel):
    snapshot: RedisWorkerReconciliationSnapshot
    detail: str
    terminal: bool


class RedisWorkerQueueHealthSnapshot(BaseModel):
    records: list[RedisWorkerReconciliationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    healthy: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
