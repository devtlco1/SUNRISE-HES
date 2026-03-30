from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerOutcome,
    RedisWorkerOutcomeRecord,
    RedisWorkerOutcomeTimeline,
    RedisWorkerProgressStage,
    RedisWorkerProgressTimeline,
)


def map_worker_progress_to_outcome_timeline(
    progress: RedisWorkerProgressTimeline,
) -> RedisWorkerOutcomeTimeline:
    redelivery_decision = str(progress.metadata.get("redelivery_decision", "retain_for_retry"))
    records: list[RedisWorkerOutcomeRecord] = [
        RedisWorkerOutcomeRecord(
            outcome=RedisWorkerOutcome.PARTIAL_SUCCESS,
            detail="worker placeholder reported partial progress",
            terminal=False,
        ),
        RedisWorkerOutcomeRecord(
            outcome=RedisWorkerOutcome.SUCCESS,
            detail="worker placeholder completed successfully",
            terminal=True,
        ),
        RedisWorkerOutcomeRecord(
            outcome=RedisWorkerOutcome.RETRYABLE_FAILURE,
            detail="worker placeholder identified retryable redelivery path",
            terminal=True,
        ),
        RedisWorkerOutcomeRecord(
            outcome=RedisWorkerOutcome.PERMANENT_FAILURE,
            detail="worker placeholder reserved permanent failure outcome",
            terminal=True,
        ),
        RedisWorkerOutcomeRecord(
            outcome=RedisWorkerOutcome.TIMEOUT,
            detail="worker placeholder reserved timeout outcome",
            terminal=True,
        ),
    ]
    if any(outcome.outcome == RedisWorkerProgressStage.REDELIVERY_PENDING for outcome in progress.outcomes):
        records[2].detail = f"worker placeholder redelivery decision: {redelivery_decision}"

    return RedisWorkerOutcomeTimeline(
        records=records,
        metadata={
            "source_identifiers": progress.metadata.get("source_identifiers"),
            "correlation_lineage": progress.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
