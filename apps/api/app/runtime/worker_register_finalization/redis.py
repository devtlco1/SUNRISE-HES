from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerCloseoutArtifact,
    RedisWorkerFinalizationArtifact,
    RedisWorkerRegisterCloseoutSummary,
    RedisWorkerRegisterFinalizationRecord,
    RedisWorkerRegisterFinalizationSummary,
)


def map_worker_register_closeout_to_register_finalization(
    register_closeout: RedisWorkerCloseoutArtifact,
) -> RedisWorkerFinalizationArtifact:
    redelivery_decision = str(
        register_closeout.metadata.get("redelivery_decision", "retain_for_retry")
    )
    closeout_types = {record.closeout_type for record in register_closeout.records}

    records = [
        RedisWorkerRegisterFinalizationRecord(
            finalization_type=RedisWorkerRegisterFinalizationSummary.NOOP_REGISTER_FINALIZATION,
            detail=(
                "worker placeholder kept register-finalization generation unchanged for inspection"
            ),
            terminal=False,
        ),
        RedisWorkerRegisterFinalizationRecord(
            finalization_type=RedisWorkerRegisterFinalizationSummary.REGISTER_FINALIZATION_SUMMARY,
            detail="worker placeholder reserved register-finalization summary artifact",
            terminal=True,
        ),
        RedisWorkerRegisterFinalizationRecord(
            finalization_type=RedisWorkerRegisterFinalizationSummary.FINALIZATION_ACTION_RECORD,
            detail=(
                "worker placeholder finalization action follows redelivery decision: "
                f"{redelivery_decision}"
            ),
            terminal=True,
        ),
        RedisWorkerRegisterFinalizationRecord(
            finalization_type=RedisWorkerRegisterFinalizationSummary.REGISTER_FINALIZATION_NOTE,
            detail="worker placeholder reserved register finalization note",
            terminal=True,
        ),
        RedisWorkerRegisterFinalizationRecord(
            finalization_type=RedisWorkerRegisterFinalizationSummary.FINAL_REGISTER_WORKFLOW_ARTIFACT,
            detail="worker placeholder reserved final register workflow artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerRegisterCloseoutSummary.REGISTER_CLOSEOUT_SUMMARY in closeout_types:
        records[1].detail = "worker placeholder would emit a register-finalization summary"
    if RedisWorkerRegisterCloseoutSummary.CLOSEOUT_ACTION_RECORD in closeout_types:
        records[
            2
        ].detail = (
            f"worker placeholder would emit a finalization-action record for {redelivery_decision}"
        )
    if RedisWorkerRegisterCloseoutSummary.REGISTER_CLOSEOUT_NOTE in closeout_types:
        records[3].detail = "worker placeholder would emit a register finalization note"
    if RedisWorkerRegisterCloseoutSummary.FINAL_REGISTER_SUMMARY_ARTIFACT in closeout_types:
        records[4].detail = "worker placeholder would emit a final register workflow artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerFinalizationArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        finalization_ready=True,
        metadata={
            "source_identifiers": register_closeout.metadata.get("source_identifiers"),
            "correlation_lineage": register_closeout.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
