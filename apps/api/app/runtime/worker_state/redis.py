from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerConsumptionResult,
    RedisWorkerState,
    RedisWorkerStateSnapshot,
    RedisWorkerStateTimeline,
    RedisWorkerStateTransition,
)


def map_worker_consumption_to_state_timeline(
    consumption: RedisWorkerConsumptionResult,
) -> RedisWorkerStateTimeline:
    source_identifiers = consumption.metadata.get("source_identifiers") or {}
    correlation_lineage = consumption.metadata.get("correlation_lineage") or {}
    pending_message_id = consumption.consume.pending_message_id
    message_id = pending_message_id
    worker_consumer_name = consumption.consume.worker_consumer_name

    snapshots = [
        RedisWorkerStateSnapshot(
            state=RedisWorkerState.PENDING,
            detail=consumption.consume.simulated_pending_state,
            worker_consumer_name=worker_consumer_name,
            pending_message_id=pending_message_id,
            message_id=message_id,
        ),
        RedisWorkerStateSnapshot(
            state=RedisWorkerState.CLAIMED,
            detail=consumption.claim.simulated_pending_state,
            worker_consumer_name=worker_consumer_name,
            pending_message_id=pending_message_id,
            message_id=message_id,
        ),
        RedisWorkerStateSnapshot(
            state=RedisWorkerState.IN_PROGRESS,
            detail=consumption.claim.claim_result,
            worker_consumer_name=worker_consumer_name,
            pending_message_id=pending_message_id,
            message_id=message_id,
        ),
        RedisWorkerStateSnapshot(
            state=RedisWorkerState.ACK_PENDING,
            detail=consumption.ack.simulated_ack_state,
            worker_consumer_name=worker_consumer_name,
            pending_message_id=pending_message_id,
            message_id=message_id,
        ),
        RedisWorkerStateSnapshot(
            state=RedisWorkerState.ACKED,
            detail=consumption.ack.ack_result,
            worker_consumer_name=worker_consumer_name,
            pending_message_id=pending_message_id,
            message_id=message_id,
        ),
        RedisWorkerStateSnapshot(
            state=RedisWorkerState.REDELIVERED,
            detail=consumption.redelivery.redelivery_result,
            worker_consumer_name=worker_consumer_name,
            pending_message_id=pending_message_id,
            message_id=message_id,
        ),
    ]
    transitions = [
        RedisWorkerStateTransition(
            from_state=RedisWorkerState.PENDING,
            to_state=RedisWorkerState.CLAIMED,
            reason="claim placeholder accepted",
        ),
        RedisWorkerStateTransition(
            from_state=RedisWorkerState.CLAIMED,
            to_state=RedisWorkerState.IN_PROGRESS,
            reason="worker processing placeholder started",
        ),
        RedisWorkerStateTransition(
            from_state=RedisWorkerState.IN_PROGRESS,
            to_state=RedisWorkerState.ACK_PENDING,
            reason="ack placeholder prepared",
        ),
        RedisWorkerStateTransition(
            from_state=RedisWorkerState.ACK_PENDING,
            to_state=RedisWorkerState.ACKED,
            reason="ack placeholder completed",
        ),
        RedisWorkerStateTransition(
            from_state=RedisWorkerState.ACKED,
            to_state=RedisWorkerState.REDELIVERED,
            reason=consumption.redelivery.redelivery_decision,
        ),
    ]
    return RedisWorkerStateTimeline(
        snapshots=snapshots,
        transitions=transitions,
        metadata={
            "source_identifiers": source_identifiers,
            "correlation_lineage": correlation_lineage,
            "redelivery_decision": consumption.redelivery.redelivery_decision,
        },
    )
