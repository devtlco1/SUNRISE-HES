from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerConfirmationArtifact,
    RedisWorkerRecoveryVerificationRecord,
    RedisWorkerRecoveryVerificationSummary,
    RedisWorkerRemediationSummary,
    RedisWorkerResponseArtifact,
)


def map_worker_remediation_to_recovery_verification(
    remediation: RedisWorkerResponseArtifact,
) -> RedisWorkerConfirmationArtifact:
    redelivery_decision = str(remediation.metadata.get("redelivery_decision", "retain_for_retry"))
    remediation_types = {record.remediation_type for record in remediation.records}

    records = [
        RedisWorkerRecoveryVerificationRecord(
            verification_type=RedisWorkerRecoveryVerificationSummary.NOOP_RECOVERY_VERIFICATION,
            detail="worker placeholder kept recovery-verification generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerRecoveryVerificationRecord(
            verification_type=RedisWorkerRecoveryVerificationSummary.RECOVERY_VERIFICATION_SUMMARY,
            detail="worker placeholder reserved recovery-verification summary artifact",
            terminal=True,
        ),
        RedisWorkerRecoveryVerificationRecord(
            verification_type=RedisWorkerRecoveryVerificationSummary.VERIFICATION_ACTION_RECORD,
            detail=f"worker placeholder verification action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerRecoveryVerificationRecord(
            verification_type=RedisWorkerRecoveryVerificationSummary.RECOVERY_CONFIRMATION_NOTE,
            detail="worker placeholder reserved recovery confirmation note",
            terminal=True,
        ),
        RedisWorkerRecoveryVerificationRecord(
            verification_type=RedisWorkerRecoveryVerificationSummary.RESPONSE_CONFIRMATION_ARTIFACT,
            detail="worker placeholder reserved response confirmation artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerRemediationSummary.REMEDIATION_SUMMARY in remediation_types:
        records[1].detail = "worker placeholder would emit a recovery-verification summary"
    if RedisWorkerRemediationSummary.RESPONSE_ACTION_RECORD in remediation_types:
        records[2].detail = (
            f"worker placeholder would emit a verification-action record for {redelivery_decision}"
        )
    if RedisWorkerRemediationSummary.REMEDIATION_NOTE in remediation_types:
        records[3].detail = "worker placeholder would emit a recovery confirmation note"
    if RedisWorkerRemediationSummary.EXCEPTION_RESPONSE_ARTIFACT in remediation_types:
        records[4].detail = "worker placeholder would emit a response confirmation artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerConfirmationArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        confirmation_ready=True,
        metadata={
            "source_identifiers": remediation.metadata.get("source_identifiers"),
            "correlation_lineage": remediation.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
