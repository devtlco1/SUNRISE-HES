from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerAuditLedger,
    RedisWorkerAuditLedgerEntry,
    RedisWorkerQueueHealthSnapshot,
    RedisWorkerReconciliationSnapshot,
    RedisWorkerVerificationRecord,
)


def map_worker_reconciliation_to_audit_ledger(
    snapshot: RedisWorkerQueueHealthSnapshot,
) -> RedisWorkerVerificationRecord:
    redelivery_decision = str(snapshot.metadata.get("redelivery_decision", "retain_for_retry"))
    snapshot_values = {record.snapshot for record in snapshot.records}

    ledger_entries = [
        RedisWorkerAuditLedgerEntry(
            entry_type=RedisWorkerAuditLedger.NOOP_AUDIT_LEDGER,
            detail="worker placeholder kept audit-ledger generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerAuditLedgerEntry(
            entry_type=RedisWorkerAuditLedger.AUDIT_LEDGER_ENTRY,
            detail="worker placeholder reserved audit-ledger entry artifact",
            terminal=True,
        ),
        RedisWorkerAuditLedgerEntry(
            entry_type=RedisWorkerAuditLedger.VERIFICATION_RECORD,
            detail=f"worker placeholder verification record follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerAuditLedgerEntry(
            entry_type=RedisWorkerAuditLedger.COMPLIANCE_READY_ENTRY,
            detail="worker placeholder reserved compliance-ready entry artifact",
            terminal=True,
        ),
        RedisWorkerAuditLedgerEntry(
            entry_type=RedisWorkerAuditLedger.RECONCILIATION_HISTORY_ENTRY,
            detail="worker placeholder reserved reconciliation history artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerReconciliationSnapshot.RECONCILIATION_SNAPSHOT in snapshot_values:
        ledger_entries[1].detail = "worker placeholder would emit an audit-ledger entry"
    if RedisWorkerReconciliationSnapshot.QUEUE_HEALTH_SNAPSHOT in snapshot_values:
        ledger_entries[2].detail = (
            f"worker placeholder would emit a verification record for {redelivery_decision}"
        )
    if RedisWorkerReconciliationSnapshot.AUDIT_READY_SNAPSHOT in snapshot_values:
        ledger_entries[3].detail = "worker placeholder would emit a compliance-ready entry"
    if RedisWorkerReconciliationSnapshot.CLOSURE_DRIFT_SNAPSHOT in snapshot_values:
        ledger_entries[4].detail = "worker placeholder would emit a reconciliation history entry"

    terminal_entries = sum(1 for entry in ledger_entries if entry.terminal)
    return RedisWorkerVerificationRecord(
        ledger_entries=ledger_entries,
        total_entries=len(ledger_entries),
        terminal_entries=terminal_entries,
        verified=True,
        metadata={
            "source_identifiers": snapshot.metadata.get("source_identifiers"),
            "correlation_lineage": snapshot.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
