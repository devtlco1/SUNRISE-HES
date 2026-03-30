from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerAttestationSealSummary,
    RedisWorkerFinalAttestationLedgerRecord,
    RedisWorkerFinalAttestationLedgerSummary,
    RedisWorkerNotarizationArtifact,
    RedisWorkerSealArtifact,
)


def map_worker_attestation_seal_to_final_attestation_ledger(
    attestation_seal: RedisWorkerSealArtifact,
) -> RedisWorkerNotarizationArtifact:
    redelivery_decision = str(
        attestation_seal.metadata.get("redelivery_decision", "retain_for_retry")
    )
    seal_types = {record.seal_type for record in attestation_seal.records}

    records = [
        RedisWorkerFinalAttestationLedgerRecord(
            ledger_type=RedisWorkerFinalAttestationLedgerSummary.NOOP_FINAL_ATTESTATION_LEDGER,
            detail="worker placeholder kept final-attestation-ledger generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerFinalAttestationLedgerRecord(
            ledger_type=RedisWorkerFinalAttestationLedgerSummary.FINAL_ATTESTATION_LEDGER_SUMMARY,
            detail="worker placeholder reserved final-attestation-ledger summary artifact",
            terminal=True,
        ),
        RedisWorkerFinalAttestationLedgerRecord(
            ledger_type=RedisWorkerFinalAttestationLedgerSummary.LEDGER_ACTION_RECORD,
            detail=f"worker placeholder ledger action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerFinalAttestationLedgerRecord(
            ledger_type=RedisWorkerFinalAttestationLedgerSummary.NOTARIZATION_NOTE,
            detail="worker placeholder reserved notarization note",
            terminal=True,
        ),
        RedisWorkerFinalAttestationLedgerRecord(
            ledger_type=RedisWorkerFinalAttestationLedgerSummary.FINAL_LEDGER_ARTIFACT,
            detail="worker placeholder reserved final ledger artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerAttestationSealSummary.ATTESTATION_SEAL_SUMMARY in seal_types:
        records[1].detail = "worker placeholder would emit a final-attestation-ledger summary"
    if RedisWorkerAttestationSealSummary.SEAL_ACTION_RECORD in seal_types:
        records[2].detail = (
            f"worker placeholder would emit a ledger-action record for {redelivery_decision}"
        )
    if RedisWorkerAttestationSealSummary.SEAL_NOTE in seal_types:
        records[3].detail = "worker placeholder would emit a notarization note"
    if RedisWorkerAttestationSealSummary.FINAL_PROOF_ARTIFACT in seal_types:
        records[4].detail = "worker placeholder would emit a final ledger artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerNotarizationArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        ledger_ready=True,
        metadata={
            "source_identifiers": attestation_seal.metadata.get("source_identifiers"),
            "correlation_lineage": attestation_seal.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
