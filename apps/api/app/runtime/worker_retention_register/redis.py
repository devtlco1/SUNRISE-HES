from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerClosureArchiveSummary,
    RedisWorkerRegisterArtifact,
    RedisWorkerRetentionArtifact,
    RedisWorkerRetentionRegisterRecord,
    RedisWorkerRetentionRegisterSummary,
)


def map_worker_closure_archive_to_retention_register(
    closure_archive: RedisWorkerRetentionArtifact,
) -> RedisWorkerRegisterArtifact:
    redelivery_decision = str(
        closure_archive.metadata.get("redelivery_decision", "retain_for_retry")
    )
    archive_types = {record.archive_type for record in closure_archive.records}

    records = [
        RedisWorkerRetentionRegisterRecord(
            register_type=RedisWorkerRetentionRegisterSummary.NOOP_RETENTION_REGISTER,
            detail="worker placeholder kept retention-register generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerRetentionRegisterRecord(
            register_type=RedisWorkerRetentionRegisterSummary.RETENTION_REGISTER_SUMMARY,
            detail="worker placeholder reserved retention-register summary artifact",
            terminal=True,
        ),
        RedisWorkerRetentionRegisterRecord(
            register_type=RedisWorkerRetentionRegisterSummary.REGISTER_ACTION_RECORD,
            detail=f"worker placeholder register action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerRetentionRegisterRecord(
            register_type=RedisWorkerRetentionRegisterSummary.RETENTION_REGISTER_NOTE,
            detail="worker placeholder reserved retention-register note",
            terminal=True,
        ),
        RedisWorkerRetentionRegisterRecord(
            register_type=RedisWorkerRetentionRegisterSummary.FINAL_REGISTER_ARTIFACT,
            detail="worker placeholder reserved final register artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerClosureArchiveSummary.CLOSURE_ARCHIVE_SUMMARY in archive_types:
        records[1].detail = "worker placeholder would emit a retention-register summary"
    if RedisWorkerClosureArchiveSummary.ARCHIVE_REGISTER_RECORD in archive_types:
        records[2].detail = (
            f"worker placeholder would emit a register-action record for {redelivery_decision}"
        )
    if RedisWorkerClosureArchiveSummary.RETENTION_NOTE in archive_types:
        records[3].detail = "worker placeholder would emit a retention-register note"
    if RedisWorkerClosureArchiveSummary.FINAL_RETENTION_ARTIFACT in archive_types:
        records[4].detail = "worker placeholder would emit a final register artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerRegisterArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        register_ready=True,
        metadata={
            "source_identifiers": closure_archive.metadata.get("source_identifiers"),
            "correlation_lineage": closure_archive.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
