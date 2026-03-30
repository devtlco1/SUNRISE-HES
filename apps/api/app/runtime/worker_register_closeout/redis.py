from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerCloseoutArtifact,
    RedisWorkerRegisterCloseArtifact,
    RedisWorkerRegisterCloseoutRecord,
    RedisWorkerRegisterCloseoutSummary,
    RedisWorkerRegisterReconciliationSummary,
)


def map_worker_register_reconciliation_to_register_closeout(
    register_reconciliation: RedisWorkerRegisterCloseArtifact,
) -> RedisWorkerCloseoutArtifact:
    redelivery_decision = str(
        register_reconciliation.metadata.get("redelivery_decision", "retain_for_retry")
    )
    reconciliation_types = {
        record.reconciliation_type for record in register_reconciliation.records
    }

    records = [
        RedisWorkerRegisterCloseoutRecord(
            closeout_type=RedisWorkerRegisterCloseoutSummary.NOOP_REGISTER_CLOSEOUT,
            detail="worker placeholder kept register-closeout generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerRegisterCloseoutRecord(
            closeout_type=RedisWorkerRegisterCloseoutSummary.REGISTER_CLOSEOUT_SUMMARY,
            detail="worker placeholder reserved register-closeout summary artifact",
            terminal=True,
        ),
        RedisWorkerRegisterCloseoutRecord(
            closeout_type=RedisWorkerRegisterCloseoutSummary.CLOSEOUT_ACTION_RECORD,
            detail=(
                "worker placeholder closeout action follows redelivery decision: "
                f"{redelivery_decision}"
            ),
            terminal=True,
        ),
        RedisWorkerRegisterCloseoutRecord(
            closeout_type=RedisWorkerRegisterCloseoutSummary.REGISTER_CLOSEOUT_NOTE,
            detail="worker placeholder reserved register closeout note",
            terminal=True,
        ),
        RedisWorkerRegisterCloseoutRecord(
            closeout_type=RedisWorkerRegisterCloseoutSummary.FINAL_REGISTER_SUMMARY_ARTIFACT,
            detail="worker placeholder reserved final register summary artifact",
            terminal=True,
        ),
    ]

    if (
        RedisWorkerRegisterReconciliationSummary.REGISTER_RECONCILIATION_SUMMARY
        in reconciliation_types
    ):
        records[1].detail = "worker placeholder would emit a register-closeout summary"
    if (
        RedisWorkerRegisterReconciliationSummary.RECONCILIATION_ACTION_RECORD
        in reconciliation_types
    ):
        records[
            2
        ].detail = (
            f"worker placeholder would emit a closeout-action record for {redelivery_decision}"
        )
    if RedisWorkerRegisterReconciliationSummary.REGISTER_CLOSE_NOTE in reconciliation_types:
        records[3].detail = "worker placeholder would emit a register closeout note"
    if (
        RedisWorkerRegisterReconciliationSummary.FINAL_REGISTER_CLOSE_ARTIFACT
        in reconciliation_types
    ):
        records[4].detail = "worker placeholder would emit a final register summary artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerCloseoutArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        closeout_ready=True,
        metadata={
            "source_identifiers": register_reconciliation.metadata.get("source_identifiers"),
            "correlation_lineage": register_reconciliation.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
