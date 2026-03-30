from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerClosureReport(StringEnum):
    BROKER_CLOSURE_SUMMARY = "broker_closure_summary"
    RECONCILIATION_READY_REPORT = "reconciliation_ready_report"
    QUEUE_OBSERVABILITY_REPORT = "queue_observability_report"
    RETENTION_SUMMARY = "retention_summary"
    NOOP_CLOSURE_REPORT = "noop_closure_report"


class RedisWorkerClosureReportRecord(BaseModel):
    report: RedisWorkerClosureReport
    detail: str
    terminal: bool


class RedisWorkerClosureReportSummary(BaseModel):
    records: list[RedisWorkerClosureReportRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    metadata: dict[str, object] = Field(default_factory=dict)
