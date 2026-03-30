from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerRegisterArtifact,
    RedisWorkerRegisterCloseArtifact,
    RedisWorkerRegisterReconciliationRecord,
    RedisWorkerRegisterReconciliationSummary,
    RedisWorkerRetentionRegisterSummary,
)


def map_worker_retention_register_to_register_reconciliation(
    retention_register: RedisWorkerRegisterArtifact,
) -> RedisWorkerRegisterCloseArtifact:
    redelivery_decision = str(
        retention_register.metadata.get("redelivery_decision", "retain_for_retry")
    )
    register_types = {record.register_type for record in retention_register.records}

    records = [
        RedisWorkerRegisterReconciliationRecord(
            reconciliation_type=RedisWorkerRegisterReconciliationSummary.NOOP_REGISTER_RECONCILIATION,
            detail="worker placeholder kept register-reconciliation generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerRegisterReconciliationRecord(
            reconciliation_type=RedisWorkerRegisterReconciliationSummary.REGISTER_RECONCILIATION_SUMMARY,
            detail="worker placeholder reserved register-reconciliation summary artifact",
            terminal=True,
        ),
        RedisWorkerRegisterReconciliationRecord(
            reconciliation_type=RedisWorkerRegisterReconciliationSummary.RECONCILIATION_ACTION_RECORD,
            detail=f"worker placeholder reconciliation action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerRegisterReconciliationRecord(
            reconciliation_type=RedisWorkerRegisterReconciliationSummary.REGISTER_CLOSE_NOTE,
            detail="worker placeholder reserved register close note",
            terminal=True,
        ),
        RedisWorkerRegisterReconciliationRecord(
            reconciliation_type=RedisWorkerRegisterReconciliationSummary.FINAL_REGISTER_CLOSE_ARTIFACT,
            detail="worker placeholder reserved final register close artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerRetentionRegisterSummary.RETENTION_REGISTER_SUMMARY in register_types:
        records[1].detail = "worker placeholder would emit a register-reconciliation summary"
    if RedisWorkerRetentionRegisterSummary.REGISTER_ACTION_RECORD in register_types:
        records[2].detail = (
            f"worker placeholder would emit a reconciliation-action record for {redelivery_decision}"
        )
    if RedisWorkerRetentionRegisterSummary.RETENTION_REGISTER_NOTE in register_types:
        records[3].detail = "worker placeholder would emit a register close note"
    if RedisWorkerRetentionRegisterSummary.FINAL_REGISTER_ARTIFACT in register_types:
        records[4].detail = "worker placeholder would emit a final register close artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerRegisterCloseArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        reconciliation_ready=True,
        metadata={
            "source_identifiers": retention_register.metadata.get("source_identifiers"),
            "correlation_lineage": retention_register.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
