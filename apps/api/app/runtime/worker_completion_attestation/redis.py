from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerCertificationArtifact,
    RedisWorkerCompletionAttestationRecord,
    RedisWorkerCompletionAttestationSummary,
    RedisWorkerCompletionProofArtifact,
    RedisWorkerResponseCertificationSummary,
)


def map_worker_response_certification_to_completion_attestation(
    response_certification: RedisWorkerCertificationArtifact,
) -> RedisWorkerCompletionProofArtifact:
    redelivery_decision = str(
        response_certification.metadata.get("redelivery_decision", "retain_for_retry")
    )
    certification_types = {
        record.certification_type for record in response_certification.records
    }

    records = [
        RedisWorkerCompletionAttestationRecord(
            attestation_type=RedisWorkerCompletionAttestationSummary.NOOP_COMPLETION_ATTESTATION,
            detail="worker placeholder kept completion-attestation generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerCompletionAttestationRecord(
            attestation_type=RedisWorkerCompletionAttestationSummary.COMPLETION_ATTESTATION_SUMMARY,
            detail="worker placeholder reserved completion-attestation summary artifact",
            terminal=True,
        ),
        RedisWorkerCompletionAttestationRecord(
            attestation_type=RedisWorkerCompletionAttestationSummary.ATTESTATION_ACTION_RECORD,
            detail=f"worker placeholder attestation action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerCompletionAttestationRecord(
            attestation_type=RedisWorkerCompletionAttestationSummary.ATTESTATION_NOTE,
            detail="worker placeholder reserved attestation note",
            terminal=True,
        ),
        RedisWorkerCompletionAttestationRecord(
            attestation_type=RedisWorkerCompletionAttestationSummary.COMPLETION_PROOF_ARTIFACT,
            detail="worker placeholder reserved completion proof artifact",
            terminal=True,
        ),
    ]

    if (
        RedisWorkerResponseCertificationSummary.RESPONSE_CERTIFICATION_SUMMARY
        in certification_types
    ):
        records[1].detail = "worker placeholder would emit a completion-attestation summary"
    if (
        RedisWorkerResponseCertificationSummary.CERTIFICATION_ACTION_RECORD
        in certification_types
    ):
        records[2].detail = (
            f"worker placeholder would emit an attestation-action record for {redelivery_decision}"
        )
    if RedisWorkerResponseCertificationSummary.CERTIFICATION_NOTE in certification_types:
        records[3].detail = "worker placeholder would emit an attestation note"
    if (
        RedisWorkerResponseCertificationSummary.COMPLETION_CERTIFICATION_ARTIFACT
        in certification_types
    ):
        records[4].detail = "worker placeholder would emit a completion proof artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerCompletionProofArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        attestation_ready=True,
        metadata={
            "source_identifiers": response_certification.metadata.get("source_identifiers"),
            "correlation_lineage": response_certification.metadata.get(
                "correlation_lineage"
            ),
            "redelivery_decision": redelivery_decision,
        },
    )
