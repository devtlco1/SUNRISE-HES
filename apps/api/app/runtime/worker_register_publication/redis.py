from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerFinalizationArtifact,
    RedisWorkerPublicationArtifact,
    RedisWorkerRegisterFinalizationSummary,
    RedisWorkerRegisterPublicationRecord,
    RedisWorkerRegisterPublicationSummary,
)


def map_worker_register_finalization_to_register_publication(
    register_finalization: RedisWorkerFinalizationArtifact,
) -> RedisWorkerPublicationArtifact:
    redelivery_decision = str(
        register_finalization.metadata.get("redelivery_decision", "retain_for_retry")
    )
    finalization_types = {record.finalization_type for record in register_finalization.records}

    records = [
        RedisWorkerRegisterPublicationRecord(
            publication_type=RedisWorkerRegisterPublicationSummary.NOOP_REGISTER_PUBLICATION,
            detail=(
                "worker placeholder kept register-publication generation unchanged for inspection"
            ),
            terminal=False,
        ),
        RedisWorkerRegisterPublicationRecord(
            publication_type=RedisWorkerRegisterPublicationSummary.REGISTER_PUBLICATION_SUMMARY,
            detail="worker placeholder reserved register-publication summary artifact",
            terminal=True,
        ),
        RedisWorkerRegisterPublicationRecord(
            publication_type=RedisWorkerRegisterPublicationSummary.PUBLICATION_ACTION_RECORD,
            detail=(
                "worker placeholder publication action follows redelivery decision: "
                f"{redelivery_decision}"
            ),
            terminal=True,
        ),
        RedisWorkerRegisterPublicationRecord(
            publication_type=RedisWorkerRegisterPublicationSummary.PUBLICATION_NOTE,
            detail="worker placeholder reserved publication note",
            terminal=True,
        ),
        RedisWorkerRegisterPublicationRecord(
            publication_type=RedisWorkerRegisterPublicationSummary.WORKFLOW_COMPLETION_ARTIFACT,
            detail="worker placeholder reserved workflow completion artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerRegisterFinalizationSummary.REGISTER_FINALIZATION_SUMMARY in finalization_types:
        records[1].detail = "worker placeholder would emit a register-publication summary"
    if RedisWorkerRegisterFinalizationSummary.FINALIZATION_ACTION_RECORD in finalization_types:
        records[
            2
        ].detail = (
            f"worker placeholder would emit a publication-action record for {redelivery_decision}"
        )
    if RedisWorkerRegisterFinalizationSummary.REGISTER_FINALIZATION_NOTE in finalization_types:
        records[3].detail = "worker placeholder would emit a publication note"
    if (
        RedisWorkerRegisterFinalizationSummary.FINAL_REGISTER_WORKFLOW_ARTIFACT
        in finalization_types
    ):
        records[4].detail = "worker placeholder would emit a workflow completion artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerPublicationArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        publication_ready=True,
        metadata={
            "source_identifiers": register_finalization.metadata.get("source_identifiers"),
            "correlation_lineage": register_finalization.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
