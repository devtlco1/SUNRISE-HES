from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerRegisterSettlementSummary,
    RedisWorkerSettlementArtifact,
    RedisWorkerSettlementAttestationRecord,
    RedisWorkerSettlementAttestationSummary,
    RedisWorkerSettlementProofArtifact,
)


def map_worker_register_settlement_to_settlement_attestation(
    register_settlement: RedisWorkerSettlementArtifact,
) -> RedisWorkerSettlementProofArtifact:
    redelivery_decision = str(
        register_settlement.metadata.get("redelivery_decision", "retain_for_retry")
    )
    settlement_types = {record.settlement_type for record in register_settlement.records}

    records = [
        RedisWorkerSettlementAttestationRecord(
            attestation_type=RedisWorkerSettlementAttestationSummary.NOOP_SETTLEMENT_ATTESTATION,
            detail=(
                "worker placeholder kept settlement-attestation generation unchanged for inspection"
            ),
            terminal=False,
        ),
        RedisWorkerSettlementAttestationRecord(
            attestation_type=RedisWorkerSettlementAttestationSummary.SETTLEMENT_ATTESTATION_SUMMARY,
            detail="worker placeholder reserved settlement-attestation summary artifact",
            terminal=True,
        ),
        RedisWorkerSettlementAttestationRecord(
            attestation_type=RedisWorkerSettlementAttestationSummary.ATTESTATION_ACTION_RECORD,
            detail=(
                "worker placeholder attestation action follows redelivery decision: "
                f"{redelivery_decision}"
            ),
            terminal=True,
        ),
        RedisWorkerSettlementAttestationRecord(
            attestation_type=RedisWorkerSettlementAttestationSummary.SETTLEMENT_ATTESTATION_NOTE,
            detail="worker placeholder reserved settlement attestation note",
            terminal=True,
        ),
        RedisWorkerSettlementAttestationRecord(
            attestation_type=RedisWorkerSettlementAttestationSummary.POST_SETTLEMENT_PROOF_ARTIFACT,
            detail="worker placeholder reserved post-settlement proof artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerRegisterSettlementSummary.REGISTER_SETTLEMENT_SUMMARY in settlement_types:
        records[1].detail = "worker placeholder would emit a settlement-attestation summary"
    if RedisWorkerRegisterSettlementSummary.SETTLEMENT_ACTION_RECORD in settlement_types:
        records[
            2
        ].detail = (
            f"worker placeholder would emit an attestation-action record for {redelivery_decision}"
        )
    if RedisWorkerRegisterSettlementSummary.REGISTER_SETTLEMENT_NOTE in settlement_types:
        records[3].detail = "worker placeholder would emit a settlement attestation note"
    if RedisWorkerRegisterSettlementSummary.POST_COMPLETION_SETTLEMENT_ARTIFACT in settlement_types:
        records[4].detail = "worker placeholder would emit a post-settlement proof artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerSettlementProofArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        attestation_ready=True,
        metadata={
            "source_identifiers": register_settlement.metadata.get("source_identifiers"),
            "correlation_lineage": register_settlement.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
