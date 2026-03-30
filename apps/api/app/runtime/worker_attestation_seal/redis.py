from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerAttestationSealRecord,
    RedisWorkerAttestationSealSummary,
    RedisWorkerCompletionAttestationSummary,
    RedisWorkerCompletionProofArtifact,
    RedisWorkerSealArtifact,
)


def map_worker_completion_attestation_to_attestation_seal(
    completion_attestation: RedisWorkerCompletionProofArtifact,
) -> RedisWorkerSealArtifact:
    redelivery_decision = str(
        completion_attestation.metadata.get("redelivery_decision", "retain_for_retry")
    )
    attestation_types = {
        record.attestation_type for record in completion_attestation.records
    }

    records = [
        RedisWorkerAttestationSealRecord(
            seal_type=RedisWorkerAttestationSealSummary.NOOP_ATTESTATION_SEAL,
            detail="worker placeholder kept attestation-seal generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerAttestationSealRecord(
            seal_type=RedisWorkerAttestationSealSummary.ATTESTATION_SEAL_SUMMARY,
            detail="worker placeholder reserved attestation-seal summary artifact",
            terminal=True,
        ),
        RedisWorkerAttestationSealRecord(
            seal_type=RedisWorkerAttestationSealSummary.SEAL_ACTION_RECORD,
            detail=f"worker placeholder seal action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerAttestationSealRecord(
            seal_type=RedisWorkerAttestationSealSummary.SEAL_NOTE,
            detail="worker placeholder reserved seal note",
            terminal=True,
        ),
        RedisWorkerAttestationSealRecord(
            seal_type=RedisWorkerAttestationSealSummary.FINAL_PROOF_ARTIFACT,
            detail="worker placeholder reserved final proof artifact",
            terminal=True,
        ),
    ]

    if (
        RedisWorkerCompletionAttestationSummary.COMPLETION_ATTESTATION_SUMMARY
        in attestation_types
    ):
        records[1].detail = "worker placeholder would emit an attestation-seal summary"
    if (
        RedisWorkerCompletionAttestationSummary.ATTESTATION_ACTION_RECORD
        in attestation_types
    ):
        records[2].detail = (
            f"worker placeholder would emit a seal-action record for {redelivery_decision}"
        )
    if RedisWorkerCompletionAttestationSummary.ATTESTATION_NOTE in attestation_types:
        records[3].detail = "worker placeholder would emit a seal note"
    if (
        RedisWorkerCompletionAttestationSummary.COMPLETION_PROOF_ARTIFACT
        in attestation_types
    ):
        records[4].detail = "worker placeholder would emit a final proof artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerSealArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        seal_ready=True,
        metadata={
            "source_identifiers": completion_attestation.metadata.get("source_identifiers"),
            "correlation_lineage": completion_attestation.metadata.get(
                "correlation_lineage"
            ),
            "redelivery_decision": redelivery_decision,
        },
    )
