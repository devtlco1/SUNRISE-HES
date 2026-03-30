from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerOutcome,
    RedisWorkerOutcomeTimeline,
    RedisWorkerResolution,
    RedisWorkerResolutionRecord,
    RedisWorkerResolutionTimeline,
)


def map_worker_outcome_to_resolution_timeline(
    outcomes: RedisWorkerOutcomeTimeline,
) -> RedisWorkerResolutionTimeline:
    redelivery_decision = str(outcomes.metadata.get("redelivery_decision", "retain_for_retry"))
    outcome_values = {record.outcome for record in outcomes.records}

    records = [
        RedisWorkerResolutionRecord(
            resolution=RedisWorkerResolution.NOOP_RESOLUTION,
            detail="worker placeholder kept broker state unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerResolutionRecord(
            resolution=RedisWorkerResolution.FINAL_ACK,
            detail="worker placeholder reserved final ack resolution",
            terminal=True,
        ),
        RedisWorkerResolutionRecord(
            resolution=RedisWorkerResolution.RETRY_SCHEDULED_HINT,
            detail=f"worker placeholder retry hint follows redelivery decision: {redelivery_decision}",
            terminal=False,
        ),
        RedisWorkerResolutionRecord(
            resolution=RedisWorkerResolution.DEAD_LETTER_PLACEHOLDER,
            detail="worker placeholder reserved dead-letter resolution",
            terminal=True,
        ),
        RedisWorkerResolutionRecord(
            resolution=RedisWorkerResolution.CANCELLATION_RESOLVED,
            detail="worker placeholder reserved cancellation resolution",
            terminal=True,
        ),
    ]

    if RedisWorkerOutcome.SUCCESS in outcome_values:
        records[1].detail = "worker placeholder would acknowledge successful completion"
    if RedisWorkerOutcome.PERMANENT_FAILURE in outcome_values:
        records[3].detail = "worker placeholder would route permanent failure to dead-letter handling"
    if RedisWorkerOutcome.CANCELLED_PLACEHOLDER in outcome_values:
        records[4].detail = "worker placeholder resolved cancellation outcome"

    return RedisWorkerResolutionTimeline(
        records=records,
        metadata={
            "source_identifiers": outcomes.metadata.get("source_identifiers"),
            "correlation_lineage": outcomes.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
