from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerDisposition,
    RedisWorkerDispositionTimeline,
    RedisWorkerFinalization,
    RedisWorkerFinalizationRecord,
    RedisWorkerFinalizationTimeline,
)


def map_worker_disposition_to_finalization_timeline(
    dispositions: RedisWorkerDispositionTimeline,
) -> RedisWorkerFinalizationTimeline:
    redelivery_decision = str(dispositions.metadata.get("redelivery_decision", "retain_for_retry"))
    disposition_values = {record.disposition for record in dispositions.records}

    records = [
        RedisWorkerFinalizationRecord(
            finalization=RedisWorkerFinalization.NOOP_FINALIZATION,
            detail="worker placeholder kept broker finalization unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerFinalizationRecord(
            finalization=RedisWorkerFinalization.RETENTION_READY_RECEIPT,
            detail="worker placeholder reserved retention-ready receipt artifact",
            terminal=True,
        ),
        RedisWorkerFinalizationRecord(
            finalization=RedisWorkerFinalization.RETRY_HANDOFF_ENVELOPE,
            detail=f"worker placeholder retry handoff follows redelivery decision: {redelivery_decision}",
            terminal=False,
        ),
        RedisWorkerFinalizationRecord(
            finalization=RedisWorkerFinalization.DEAD_LETTER_HANDOFF_RECORD,
            detail="worker placeholder reserved dead-letter handoff artifact",
            terminal=True,
        ),
        RedisWorkerFinalizationRecord(
            finalization=RedisWorkerFinalization.CANCELLATION_FINALIZED_MARKER,
            detail="worker placeholder reserved cancellation finalized marker",
            terminal=True,
        ),
    ]

    if RedisWorkerDisposition.ARCHIVE_READY in disposition_values:
        records[1].detail = "worker placeholder would emit a retention-ready receipt"
    if RedisWorkerDisposition.DEAD_LETTER_READY in disposition_values:
        records[3].detail = "worker placeholder would emit a dead-letter handoff record"
    if RedisWorkerDisposition.CANCELLATION_CLOSED in disposition_values:
        records[4].detail = "worker placeholder would finalize cancelled work"

    return RedisWorkerFinalizationTimeline(
        records=records,
        metadata={
            "source_identifiers": dispositions.metadata.get("source_identifiers"),
            "correlation_lineage": dispositions.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
