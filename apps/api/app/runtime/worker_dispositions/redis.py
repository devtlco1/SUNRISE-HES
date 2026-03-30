from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerDisposition,
    RedisWorkerDispositionRecord,
    RedisWorkerDispositionTimeline,
    RedisWorkerResolution,
    RedisWorkerResolutionTimeline,
)


def map_worker_resolution_to_disposition_timeline(
    resolutions: RedisWorkerResolutionTimeline,
) -> RedisWorkerDispositionTimeline:
    redelivery_decision = str(resolutions.metadata.get("redelivery_decision", "retain_for_retry"))
    resolution_values = {record.resolution for record in resolutions.records}

    records = [
        RedisWorkerDispositionRecord(
            disposition=RedisWorkerDisposition.NOOP_DISPOSITION,
            detail="worker placeholder kept broker disposition unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerDispositionRecord(
            disposition=RedisWorkerDisposition.ARCHIVE_READY,
            detail="worker placeholder reserved archive-ready disposition",
            terminal=True,
        ),
        RedisWorkerDispositionRecord(
            disposition=RedisWorkerDisposition.RETRY_QUEUE_READY,
            detail=f"worker placeholder retry-queue disposition follows redelivery decision: {redelivery_decision}",
            terminal=False,
        ),
        RedisWorkerDispositionRecord(
            disposition=RedisWorkerDisposition.DEAD_LETTER_READY,
            detail="worker placeholder reserved dead-letter-ready disposition",
            terminal=True,
        ),
        RedisWorkerDispositionRecord(
            disposition=RedisWorkerDisposition.CANCELLATION_CLOSED,
            detail="worker placeholder reserved cancellation-closed disposition",
            terminal=True,
        ),
    ]

    if RedisWorkerResolution.FINAL_ACK in resolution_values:
        records[1].detail = "worker placeholder would archive ack-resolved work"
    if RedisWorkerResolution.DEAD_LETTER_PLACEHOLDER in resolution_values:
        records[3].detail = "worker placeholder would mark work as dead-letter ready"
    if RedisWorkerResolution.CANCELLATION_RESOLVED in resolution_values:
        records[4].detail = "worker placeholder would close cancelled work"

    return RedisWorkerDispositionTimeline(
        records=records,
        metadata={
            "source_identifiers": resolutions.metadata.get("source_identifiers"),
            "correlation_lineage": resolutions.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
