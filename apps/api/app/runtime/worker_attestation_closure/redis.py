from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerAttestationClosureRecord,
    RedisWorkerAttestationClosureSummary,
    RedisWorkerClosureProofArtifact,
    RedisWorkerSettlementAttestationSummary,
    RedisWorkerSettlementProofArtifact,
)


def map_worker_settlement_attestation_to_attestation_closure(
    settlement_attestation: RedisWorkerSettlementProofArtifact,
) -> RedisWorkerClosureProofArtifact:
    redelivery_decision = str(
        settlement_attestation.metadata.get("redelivery_decision", "retain_for_retry")
    )
    attestation_types = {record.attestation_type for record in settlement_attestation.records}

    records = [
        RedisWorkerAttestationClosureRecord(
            closure_type=RedisWorkerAttestationClosureSummary.NOOP_ATTESTATION_CLOSURE,
            detail=(
                "worker placeholder kept attestation-closure generation unchanged for inspection"
            ),
            terminal=False,
        ),
        RedisWorkerAttestationClosureRecord(
            closure_type=RedisWorkerAttestationClosureSummary.ATTESTATION_CLOSURE_SUMMARY,
            detail="worker placeholder reserved attestation-closure summary artifact",
            terminal=True,
        ),
        RedisWorkerAttestationClosureRecord(
            closure_type=RedisWorkerAttestationClosureSummary.CLOSURE_ACTION_RECORD,
            detail=(
                "worker placeholder closure action follows redelivery decision: "
                f"{redelivery_decision}"
            ),
            terminal=True,
        ),
        RedisWorkerAttestationClosureRecord(
            closure_type=RedisWorkerAttestationClosureSummary.ATTESTATION_CLOSURE_NOTE,
            detail="worker placeholder reserved attestation closure note",
            terminal=True,
        ),
        RedisWorkerAttestationClosureRecord(
            closure_type=(RedisWorkerAttestationClosureSummary.POST_ATTESTATION_CLOSURE_ARTIFACT),
            detail="worker placeholder reserved post-attestation closure artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerSettlementAttestationSummary.SETTLEMENT_ATTESTATION_SUMMARY in attestation_types:
        records[1].detail = "worker placeholder would emit an attestation-closure summary"
    if RedisWorkerSettlementAttestationSummary.ATTESTATION_ACTION_RECORD in attestation_types:
        records[
            2
        ].detail = (
            f"worker placeholder would emit a closure-action record for {redelivery_decision}"
        )
    if RedisWorkerSettlementAttestationSummary.SETTLEMENT_ATTESTATION_NOTE in attestation_types:
        records[3].detail = "worker placeholder would emit an attestation closure note"
    if RedisWorkerSettlementAttestationSummary.POST_SETTLEMENT_PROOF_ARTIFACT in attestation_types:
        records[4].detail = "worker placeholder would emit a post-attestation closure artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerClosureProofArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        closure_ready=True,
        metadata={
            "source_identifiers": settlement_attestation.metadata.get("source_identifiers"),
            "correlation_lineage": settlement_attestation.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
