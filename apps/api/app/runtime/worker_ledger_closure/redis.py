from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerArchivalArtifact,
    RedisWorkerFinalAttestationLedgerSummary,
    RedisWorkerLedgerClosureRecord,
    RedisWorkerLedgerClosureSummary,
    RedisWorkerNotarizationArtifact,
)


def map_worker_final_attestation_ledger_to_ledger_closure(
    final_attestation_ledger: RedisWorkerNotarizationArtifact,
) -> RedisWorkerArchivalArtifact:
    redelivery_decision = str(
        final_attestation_ledger.metadata.get("redelivery_decision", "retain_for_retry")
    )
    ledger_types = {record.ledger_type for record in final_attestation_ledger.records}

    records = [
        RedisWorkerLedgerClosureRecord(
            closure_type=RedisWorkerLedgerClosureSummary.NOOP_LEDGER_CLOSURE,
            detail="worker placeholder kept ledger-closure generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerLedgerClosureRecord(
            closure_type=RedisWorkerLedgerClosureSummary.LEDGER_CLOSURE_SUMMARY,
            detail="worker placeholder reserved ledger-closure summary artifact",
            terminal=True,
        ),
        RedisWorkerLedgerClosureRecord(
            closure_type=RedisWorkerLedgerClosureSummary.ARCHIVAL_ACTION_RECORD,
            detail=f"worker placeholder archival action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerLedgerClosureRecord(
            closure_type=RedisWorkerLedgerClosureSummary.CLOSURE_NOTE,
            detail="worker placeholder reserved closure note",
            terminal=True,
        ),
        RedisWorkerLedgerClosureRecord(
            closure_type=RedisWorkerLedgerClosureSummary.ARCHIVAL_PROOF_ARTIFACT,
            detail="worker placeholder reserved archival proof artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerFinalAttestationLedgerSummary.FINAL_ATTESTATION_LEDGER_SUMMARY in ledger_types:
        records[1].detail = "worker placeholder would emit a ledger-closure summary"
    if RedisWorkerFinalAttestationLedgerSummary.LEDGER_ACTION_RECORD in ledger_types:
        records[2].detail = (
            f"worker placeholder would emit an archival-action record for {redelivery_decision}"
        )
    if RedisWorkerFinalAttestationLedgerSummary.NOTARIZATION_NOTE in ledger_types:
        records[3].detail = "worker placeholder would emit a closure note"
    if RedisWorkerFinalAttestationLedgerSummary.FINAL_LEDGER_ARTIFACT in ledger_types:
        records[4].detail = "worker placeholder would emit an archival proof artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerArchivalArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        closure_ready=True,
        metadata={
            "source_identifiers": final_attestation_ledger.metadata.get("source_identifiers"),
            "correlation_lineage": final_attestation_ledger.metadata.get(
                "correlation_lineage"
            ),
            "redelivery_decision": redelivery_decision,
        },
    )
