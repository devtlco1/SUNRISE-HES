from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerClosureReport,
    RedisWorkerClosureReportSummary,
    RedisWorkerQueueHealthSnapshot,
    RedisWorkerReconciliationRecord,
    RedisWorkerReconciliationSnapshot,
)


def map_worker_closure_report_to_reconciliation_snapshot(
    report: RedisWorkerClosureReportSummary,
) -> RedisWorkerQueueHealthSnapshot:
    redelivery_decision = str(report.metadata.get("redelivery_decision", "retain_for_retry"))
    report_values = {record.report for record in report.records}

    records = [
        RedisWorkerReconciliationRecord(
            snapshot=RedisWorkerReconciliationSnapshot.NOOP_RECONCILIATION_SNAPSHOT,
            detail="worker placeholder kept reconciliation snapshot unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerReconciliationRecord(
            snapshot=RedisWorkerReconciliationSnapshot.RECONCILIATION_SNAPSHOT,
            detail="worker placeholder reserved reconciliation snapshot artifact",
            terminal=True,
        ),
        RedisWorkerReconciliationRecord(
            snapshot=RedisWorkerReconciliationSnapshot.QUEUE_HEALTH_SNAPSHOT,
            detail=f"worker placeholder queue health follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerReconciliationRecord(
            snapshot=RedisWorkerReconciliationSnapshot.CLOSURE_DRIFT_SNAPSHOT,
            detail="worker placeholder reserved closure drift snapshot artifact",
            terminal=True,
        ),
        RedisWorkerReconciliationRecord(
            snapshot=RedisWorkerReconciliationSnapshot.AUDIT_READY_SNAPSHOT,
            detail="worker placeholder reserved audit-ready snapshot artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerClosureReport.BROKER_CLOSURE_SUMMARY in report_values:
        records[1].detail = "worker placeholder would emit a reconciliation snapshot"
    if RedisWorkerClosureReport.RECONCILIATION_READY_REPORT in report_values:
        records[2].detail = (
            f"worker placeholder would emit a queue health snapshot for {redelivery_decision}"
        )
    if RedisWorkerClosureReport.QUEUE_OBSERVABILITY_REPORT in report_values:
        records[3].detail = "worker placeholder would emit a closure drift snapshot"
    if RedisWorkerClosureReport.RETENTION_SUMMARY in report_values:
        records[4].detail = "worker placeholder would emit an audit-ready snapshot"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerQueueHealthSnapshot(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        healthy=True,
        metadata={
            "source_identifiers": report.metadata.get("source_identifiers"),
            "correlation_lineage": report.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
