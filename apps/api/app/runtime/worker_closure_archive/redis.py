from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerArchivalArtifact,
    RedisWorkerClosureArchiveRecord,
    RedisWorkerClosureArchiveSummary,
    RedisWorkerLedgerClosureSummary,
    RedisWorkerRetentionArtifact,
)


def map_worker_ledger_closure_to_closure_archive(
    ledger_closure: RedisWorkerArchivalArtifact,
) -> RedisWorkerRetentionArtifact:
    redelivery_decision = str(
        ledger_closure.metadata.get("redelivery_decision", "retain_for_retry")
    )
    closure_types = {record.closure_type for record in ledger_closure.records}

    records = [
        RedisWorkerClosureArchiveRecord(
            archive_type=RedisWorkerClosureArchiveSummary.NOOP_CLOSURE_ARCHIVE,
            detail="worker placeholder kept closure-archive generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerClosureArchiveRecord(
            archive_type=RedisWorkerClosureArchiveSummary.CLOSURE_ARCHIVE_SUMMARY,
            detail="worker placeholder reserved closure-archive summary artifact",
            terminal=True,
        ),
        RedisWorkerClosureArchiveRecord(
            archive_type=RedisWorkerClosureArchiveSummary.ARCHIVE_REGISTER_RECORD,
            detail=f"worker placeholder archive register follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerClosureArchiveRecord(
            archive_type=RedisWorkerClosureArchiveSummary.RETENTION_NOTE,
            detail="worker placeholder reserved retention note",
            terminal=True,
        ),
        RedisWorkerClosureArchiveRecord(
            archive_type=RedisWorkerClosureArchiveSummary.FINAL_RETENTION_ARTIFACT,
            detail="worker placeholder reserved final retention artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerLedgerClosureSummary.LEDGER_CLOSURE_SUMMARY in closure_types:
        records[1].detail = "worker placeholder would emit a closure-archive summary"
    if RedisWorkerLedgerClosureSummary.ARCHIVAL_ACTION_RECORD in closure_types:
        records[2].detail = (
            f"worker placeholder would emit an archive-register record for {redelivery_decision}"
        )
    if RedisWorkerLedgerClosureSummary.CLOSURE_NOTE in closure_types:
        records[3].detail = "worker placeholder would emit a retention note"
    if RedisWorkerLedgerClosureSummary.ARCHIVAL_PROOF_ARTIFACT in closure_types:
        records[4].detail = "worker placeholder would emit a final retention artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerRetentionArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        archive_ready=True,
        metadata={
            "source_identifiers": ledger_closure.metadata.get("source_identifiers"),
            "correlation_lineage": ledger_closure.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
