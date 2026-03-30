from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerAssuranceArtifact,
    RedisWorkerConfirmationArtifact,
    RedisWorkerRecoveryVerificationSummary,
    RedisWorkerResponseAssuranceRecord,
    RedisWorkerResponseAssuranceSummary,
)


def map_worker_recovery_verification_to_response_assurance(
    recovery_verification: RedisWorkerConfirmationArtifact,
) -> RedisWorkerAssuranceArtifact:
    redelivery_decision = str(
        recovery_verification.metadata.get("redelivery_decision", "retain_for_retry")
    )
    verification_types = {
        record.verification_type for record in recovery_verification.records
    }

    records = [
        RedisWorkerResponseAssuranceRecord(
            assurance_type=RedisWorkerResponseAssuranceSummary.NOOP_RESPONSE_ASSURANCE,
            detail="worker placeholder kept response-assurance generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerResponseAssuranceRecord(
            assurance_type=RedisWorkerResponseAssuranceSummary.RESPONSE_ASSURANCE_SUMMARY,
            detail="worker placeholder reserved response-assurance summary artifact",
            terminal=True,
        ),
        RedisWorkerResponseAssuranceRecord(
            assurance_type=RedisWorkerResponseAssuranceSummary.ASSURANCE_ACTION_RECORD,
            detail=f"worker placeholder assurance action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerResponseAssuranceRecord(
            assurance_type=RedisWorkerResponseAssuranceSummary.ASSURANCE_NOTE,
            detail="worker placeholder reserved assurance note",
            terminal=True,
        ),
        RedisWorkerResponseAssuranceRecord(
            assurance_type=RedisWorkerResponseAssuranceSummary.POST_VERIFICATION_ARTIFACT,
            detail="worker placeholder reserved post-verification artifact",
            terminal=True,
        ),
    ]

    if (
        RedisWorkerRecoveryVerificationSummary.RECOVERY_VERIFICATION_SUMMARY
        in verification_types
    ):
        records[1].detail = "worker placeholder would emit a response-assurance summary"
    if RedisWorkerRecoveryVerificationSummary.VERIFICATION_ACTION_RECORD in verification_types:
        records[2].detail = (
            f"worker placeholder would emit an assurance-action record for {redelivery_decision}"
        )
    if RedisWorkerRecoveryVerificationSummary.RECOVERY_CONFIRMATION_NOTE in verification_types:
        records[3].detail = "worker placeholder would emit an assurance note"
    if (
        RedisWorkerRecoveryVerificationSummary.RESPONSE_CONFIRMATION_ARTIFACT
        in verification_types
    ):
        records[4].detail = "worker placeholder would emit a post-verification artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerAssuranceArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        assurance_ready=True,
        metadata={
            "source_identifiers": recovery_verification.metadata.get("source_identifiers"),
            "correlation_lineage": recovery_verification.metadata.get(
                "correlation_lineage"
            ),
            "redelivery_decision": redelivery_decision,
        },
    )
