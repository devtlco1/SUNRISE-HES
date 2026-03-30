from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerCompletionArtifact,
    RedisWorkerRegisterCompletionSummary,
    RedisWorkerRegisterSettlementRecord,
    RedisWorkerRegisterSettlementSummary,
    RedisWorkerSettlementArtifact,
)


def map_worker_register_completion_to_register_settlement(
    register_completion: RedisWorkerCompletionArtifact,
) -> RedisWorkerSettlementArtifact:
    redelivery_decision = str(
        register_completion.metadata.get("redelivery_decision", "retain_for_retry")
    )
    completion_types = {record.completion_type for record in register_completion.records}

    records = [
        RedisWorkerRegisterSettlementRecord(
            settlement_type=RedisWorkerRegisterSettlementSummary.NOOP_REGISTER_SETTLEMENT,
            detail=(
                "worker placeholder kept register-settlement generation unchanged for inspection"
            ),
            terminal=False,
        ),
        RedisWorkerRegisterSettlementRecord(
            settlement_type=RedisWorkerRegisterSettlementSummary.REGISTER_SETTLEMENT_SUMMARY,
            detail="worker placeholder reserved register-settlement summary artifact",
            terminal=True,
        ),
        RedisWorkerRegisterSettlementRecord(
            settlement_type=RedisWorkerRegisterSettlementSummary.SETTLEMENT_ACTION_RECORD,
            detail=(
                "worker placeholder settlement action follows redelivery decision: "
                f"{redelivery_decision}"
            ),
            terminal=True,
        ),
        RedisWorkerRegisterSettlementRecord(
            settlement_type=RedisWorkerRegisterSettlementSummary.REGISTER_SETTLEMENT_NOTE,
            detail="worker placeholder reserved register settlement note",
            terminal=True,
        ),
        RedisWorkerRegisterSettlementRecord(
            settlement_type=(
                RedisWorkerRegisterSettlementSummary.POST_COMPLETION_SETTLEMENT_ARTIFACT
            ),
            detail="worker placeholder reserved post-completion settlement artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerRegisterCompletionSummary.REGISTER_COMPLETION_SUMMARY in completion_types:
        records[1].detail = "worker placeholder would emit a register-settlement summary"
    if RedisWorkerRegisterCompletionSummary.COMPLETION_ACTION_RECORD in completion_types:
        records[
            2
        ].detail = (
            f"worker placeholder would emit a settlement-action record for {redelivery_decision}"
        )
    if RedisWorkerRegisterCompletionSummary.REGISTER_COMPLETION_NOTE in completion_types:
        records[3].detail = "worker placeholder would emit a register settlement note"
    if (
        RedisWorkerRegisterCompletionSummary.POST_PUBLICATION_COMPLETION_ARTIFACT
        in completion_types
    ):
        records[4].detail = "worker placeholder would emit a post-completion settlement artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerSettlementArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        settlement_ready=True,
        metadata={
            "source_identifiers": register_completion.metadata.get("source_identifiers"),
            "correlation_lineage": register_completion.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
