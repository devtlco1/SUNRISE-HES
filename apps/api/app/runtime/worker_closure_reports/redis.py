from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerClosureReport,
    RedisWorkerClosureReportRecord,
    RedisWorkerClosureReportSummary,
    RedisWorkerFinalization,
    RedisWorkerFinalizationTimeline,
)


def map_worker_finalization_to_closure_report(
    finalizations: RedisWorkerFinalizationTimeline,
) -> RedisWorkerClosureReportSummary:
    redelivery_decision = str(finalizations.metadata.get("redelivery_decision", "retain_for_retry"))
    finalization_values = {record.finalization for record in finalizations.records}

    records = [
        RedisWorkerClosureReportRecord(
            report=RedisWorkerClosureReport.NOOP_CLOSURE_REPORT,
            detail="worker placeholder kept broker closure reporting unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerClosureReportRecord(
            report=RedisWorkerClosureReport.BROKER_CLOSURE_SUMMARY,
            detail="worker placeholder reserved broker closure summary artifact",
            terminal=True,
        ),
        RedisWorkerClosureReportRecord(
            report=RedisWorkerClosureReport.RECONCILIATION_READY_REPORT,
            detail=f"worker placeholder reconciliation report follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerClosureReportRecord(
            report=RedisWorkerClosureReport.QUEUE_OBSERVABILITY_REPORT,
            detail="worker placeholder reserved queue observability report artifact",
            terminal=True,
        ),
        RedisWorkerClosureReportRecord(
            report=RedisWorkerClosureReport.RETENTION_SUMMARY,
            detail="worker placeholder reserved retention summary artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerFinalization.RETENTION_READY_RECEIPT in finalization_values:
        records[1].detail = "worker placeholder would emit a broker closure summary"
        records[4].detail = "worker placeholder would emit a retention summary"
    if RedisWorkerFinalization.RETRY_HANDOFF_ENVELOPE in finalization_values:
        records[2].detail = (
            f"worker placeholder would emit a reconciliation-ready report for {redelivery_decision}"
        )
    if RedisWorkerFinalization.DEAD_LETTER_HANDOFF_RECORD in finalization_values:
        records[3].detail = "worker placeholder would emit a dead-letter observability report"
    if RedisWorkerFinalization.CANCELLATION_FINALIZED_MARKER in finalization_values:
        records[3].detail = "worker placeholder would emit a cancellation observability report"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerClosureReportSummary(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        metadata={
            "source_identifiers": finalizations.metadata.get("source_identifiers"),
            "correlation_lineage": finalizations.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
