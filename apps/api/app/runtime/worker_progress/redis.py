from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerProgressCheckpoint,
    RedisWorkerProgressOutcome,
    RedisWorkerProgressStage,
    RedisWorkerState,
    RedisWorkerStateTimeline,
    RedisWorkerProgressTimeline,
)


def map_worker_state_to_progress_timeline(
    timeline: RedisWorkerStateTimeline,
) -> RedisWorkerProgressTimeline:
    source_identifiers = timeline.metadata.get("source_identifiers") or {}
    correlation_lineage = timeline.metadata.get("correlation_lineage") or {}
    redelivery_decision = str(timeline.metadata.get("redelivery_decision", "retain_for_retry"))

    checkpoints: list[RedisWorkerProgressCheckpoint] = []
    for snapshot in timeline.snapshots:
        stage = _map_state_to_progress_stage(snapshot.state)
        checkpoints.append(
            RedisWorkerProgressCheckpoint(
                stage=stage,
                detail=snapshot.detail,
                worker_consumer_name=snapshot.worker_consumer_name,
                message_id=snapshot.message_id,
            )
        )

    outcomes = [
        RedisWorkerProgressOutcome(
            outcome=RedisWorkerProgressStage.PARTIALLY_PROCESSED,
            detail="worker placeholder processed message partially",
            redelivery_decision=None,
        ),
        RedisWorkerProgressOutcome(
            outcome=RedisWorkerProgressStage.COMPLETED_PLACEHOLDER,
            detail="worker placeholder completed processing path",
            redelivery_decision=None,
        ),
        RedisWorkerProgressOutcome(
            outcome=RedisWorkerProgressStage.REDELIVERY_PENDING,
            detail="worker placeholder evaluated redelivery outcome",
            redelivery_decision=redelivery_decision,
        ),
    ]
    return RedisWorkerProgressTimeline(
        checkpoints=checkpoints,
        outcomes=outcomes,
        metadata={
            "source_identifiers": source_identifiers,
            "correlation_lineage": correlation_lineage,
            "redelivery_decision": redelivery_decision,
        },
    )


def _map_state_to_progress_stage(state: RedisWorkerState) -> RedisWorkerProgressStage:
    if state == RedisWorkerState.PENDING:
        return RedisWorkerProgressStage.STARTED
    if state == RedisWorkerState.CLAIMED:
        return RedisWorkerProgressStage.CHECKPOINT_REACHED
    if state == RedisWorkerState.IN_PROGRESS:
        return RedisWorkerProgressStage.PARTIALLY_PROCESSED
    if state == RedisWorkerState.ACK_PENDING:
        return RedisWorkerProgressStage.WAITING_FOR_ACK
    if state == RedisWorkerState.ACKED:
        return RedisWorkerProgressStage.COMPLETED_PLACEHOLDER
    if state == RedisWorkerState.REDELIVERED:
        return RedisWorkerProgressStage.REDELIVERY_PENDING
    return RedisWorkerProgressStage.STALLED_PLACEHOLDER
