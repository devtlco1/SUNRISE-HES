from __future__ import annotations

from app.runtime.contracts import (
    RedisMessageLifecycleContract,
    RedisWorkerAckResult,
    RedisWorkerClaimResult,
    RedisWorkerConsumeContract,
    RedisWorkerConsumptionResult,
    RedisWorkerRedeliveryResult,
)


def map_lifecycle_to_worker_consumption(
    lifecycle: RedisMessageLifecycleContract,
) -> RedisWorkerConsumptionResult:
    consume = RedisWorkerConsumeContract(
        dequeue_result="dequeued_placeholder",
        worker_consumer_name=lifecycle.dequeue.consumer_name,
        pending_message_id=lifecycle.dequeue.pending_message_id,
        simulated_pending_state="pending_claimable",
    )
    claim = RedisWorkerClaimResult(
        claim_result="claim_ready_placeholder",
        claim_token=lifecycle.claim.claim_token,
        lease_expiration_seconds=lifecycle.claim.claim_timeout_seconds,
        simulated_pending_state="claimed_placeholder",
    )
    ack = RedisWorkerAckResult(
        ack_result="ack_ready_placeholder",
        ack_token=lifecycle.ack.ack_token,
        simulated_ack_state="ack_pending_placeholder",
    )
    redelivery = RedisWorkerRedeliveryResult(
        redelivery_result="redelivery_evaluated_placeholder",
        redelivery_decision="retain_for_retry" if lifecycle.redelivery.retry_claim_hint else "dead_letter_candidate",
        redelivery_count=lifecycle.redelivery.redelivery_count,
    )
    return RedisWorkerConsumptionResult(
        consume=consume,
        claim=claim,
        ack=ack,
        redelivery=redelivery,
        metadata={
            "routing_key": lifecycle.metadata.get("routing_key"),
            "source_identifiers": lifecycle.metadata.get("source_identifiers"),
            "correlation_lineage": lifecycle.metadata.get("correlation_lineage"),
        },
    )
