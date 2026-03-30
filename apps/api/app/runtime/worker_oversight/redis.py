from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerApprovalArtifact,
    RedisWorkerControlPlaneSummary,
    RedisWorkerInterventionArtifact,
    RedisWorkerOversightRecord,
    RedisWorkerOversightSummary,
)


def map_worker_control_plane_to_oversight(
    control_plane: RedisWorkerApprovalArtifact,
) -> RedisWorkerInterventionArtifact:
    redelivery_decision = str(control_plane.metadata.get("redelivery_decision", "retain_for_retry"))
    control_types = {record.control_type for record in control_plane.records}

    records = [
        RedisWorkerOversightRecord(
            oversight_type=RedisWorkerOversightSummary.NOOP_OVERSIGHT,
            detail="worker placeholder kept operations-oversight generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerOversightRecord(
            oversight_type=RedisWorkerOversightSummary.OVERSIGHT_SUMMARY,
            detail="worker placeholder reserved oversight summary artifact",
            terminal=True,
        ),
        RedisWorkerOversightRecord(
            oversight_type=RedisWorkerOversightSummary.INTERVENTION_CANDIDATE_RECORD,
            detail=f"worker placeholder intervention flow follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerOversightRecord(
            oversight_type=RedisWorkerOversightSummary.OPERATIONS_WATCH_NOTE,
            detail="worker placeholder reserved operations watch note",
            terminal=True,
        ),
        RedisWorkerOversightRecord(
            oversight_type=RedisWorkerOversightSummary.ESCALATION_REVIEW_ARTIFACT,
            detail="worker placeholder reserved escalation review artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerControlPlaneSummary.CONTROL_PLANE_SUMMARY in control_types:
        records[1].detail = "worker placeholder would emit an operations oversight summary"
    if RedisWorkerControlPlaneSummary.APPROVAL_REQUIRED_RECORD in control_types:
        records[2].detail = (
            f"worker placeholder would emit an intervention-candidate record for {redelivery_decision}"
        )
    if RedisWorkerControlPlaneSummary.BROKER_OPERATIONS_NOTE in control_types:
        records[3].detail = "worker placeholder would emit an operations watch note"
    if RedisWorkerControlPlaneSummary.CONTROL_REVIEW_ARTIFACT in control_types:
        records[4].detail = "worker placeholder would emit an escalation review artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerInterventionArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        intervention_ready=True,
        metadata={
            "source_identifiers": control_plane.metadata.get("source_identifiers"),
            "correlation_lineage": control_plane.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
