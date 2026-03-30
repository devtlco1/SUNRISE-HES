from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerCompletionArtifact,
    RedisWorkerPublicationArtifact,
    RedisWorkerRegisterCompletionRecord,
    RedisWorkerRegisterCompletionSummary,
    RedisWorkerRegisterPublicationSummary,
)


def map_worker_register_publication_to_register_completion(
    register_publication: RedisWorkerPublicationArtifact,
) -> RedisWorkerCompletionArtifact:
    redelivery_decision = str(
        register_publication.metadata.get("redelivery_decision", "retain_for_retry")
    )
    publication_types = {record.publication_type for record in register_publication.records}

    records = [
        RedisWorkerRegisterCompletionRecord(
            completion_type=RedisWorkerRegisterCompletionSummary.NOOP_REGISTER_COMPLETION,
            detail=(
                "worker placeholder kept register-completion generation unchanged for inspection"
            ),
            terminal=False,
        ),
        RedisWorkerRegisterCompletionRecord(
            completion_type=RedisWorkerRegisterCompletionSummary.REGISTER_COMPLETION_SUMMARY,
            detail="worker placeholder reserved register-completion summary artifact",
            terminal=True,
        ),
        RedisWorkerRegisterCompletionRecord(
            completion_type=RedisWorkerRegisterCompletionSummary.COMPLETION_ACTION_RECORD,
            detail=(
                "worker placeholder completion action follows redelivery decision: "
                f"{redelivery_decision}"
            ),
            terminal=True,
        ),
        RedisWorkerRegisterCompletionRecord(
            completion_type=RedisWorkerRegisterCompletionSummary.REGISTER_COMPLETION_NOTE,
            detail="worker placeholder reserved register completion note",
            terminal=True,
        ),
        RedisWorkerRegisterCompletionRecord(
            completion_type=(
                RedisWorkerRegisterCompletionSummary.POST_PUBLICATION_COMPLETION_ARTIFACT
            ),
            detail="worker placeholder reserved post-publication completion artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerRegisterPublicationSummary.REGISTER_PUBLICATION_SUMMARY in publication_types:
        records[1].detail = "worker placeholder would emit a register-completion summary"
    if RedisWorkerRegisterPublicationSummary.PUBLICATION_ACTION_RECORD in publication_types:
        records[
            2
        ].detail = (
            f"worker placeholder would emit a completion-action record for {redelivery_decision}"
        )
    if RedisWorkerRegisterPublicationSummary.PUBLICATION_NOTE in publication_types:
        records[3].detail = "worker placeholder would emit a register completion note"
    if RedisWorkerRegisterPublicationSummary.WORKFLOW_COMPLETION_ARTIFACT in publication_types:
        records[4].detail = "worker placeholder would emit a post-publication completion artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerCompletionArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        completion_ready=True,
        metadata={
            "source_identifiers": register_publication.metadata.get("source_identifiers"),
            "correlation_lineage": register_publication.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
