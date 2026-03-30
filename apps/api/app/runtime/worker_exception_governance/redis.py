from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerExceptionGovernanceRecord,
    RedisWorkerExceptionGovernanceSummary,
    RedisWorkerInterventionArtifact,
    RedisWorkerInterventionDecision,
    RedisWorkerOversightSummary,
)


def map_worker_oversight_to_exception_governance(
    oversight: RedisWorkerInterventionArtifact,
) -> RedisWorkerInterventionDecision:
    redelivery_decision = str(oversight.metadata.get("redelivery_decision", "retain_for_retry"))
    oversight_types = {record.oversight_type for record in oversight.records}

    records = [
        RedisWorkerExceptionGovernanceRecord(
            governance_type=RedisWorkerExceptionGovernanceSummary.NOOP_EXCEPTION_GOVERNANCE,
            detail="worker placeholder kept exception-governance generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerExceptionGovernanceRecord(
            governance_type=RedisWorkerExceptionGovernanceSummary.EXCEPTION_GOVERNANCE_SUMMARY,
            detail="worker placeholder reserved exception-governance summary artifact",
            terminal=True,
        ),
        RedisWorkerExceptionGovernanceRecord(
            governance_type=RedisWorkerExceptionGovernanceSummary.INTERVENTION_DECISION_RECORD,
            detail=f"worker placeholder intervention decision follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerExceptionGovernanceRecord(
            governance_type=RedisWorkerExceptionGovernanceSummary.EXCEPTION_REVIEW_NOTE,
            detail="worker placeholder reserved exception review note",
            terminal=True,
        ),
        RedisWorkerExceptionGovernanceRecord(
            governance_type=RedisWorkerExceptionGovernanceSummary.GOVERNANCE_EXCEPTION_ARTIFACT,
            detail="worker placeholder reserved governance exception artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerOversightSummary.OVERSIGHT_SUMMARY in oversight_types:
        records[1].detail = "worker placeholder would emit an exception-governance summary"
    if RedisWorkerOversightSummary.INTERVENTION_CANDIDATE_RECORD in oversight_types:
        records[2].detail = (
            f"worker placeholder would emit an intervention-decision record for {redelivery_decision}"
        )
    if RedisWorkerOversightSummary.OPERATIONS_WATCH_NOTE in oversight_types:
        records[3].detail = "worker placeholder would emit an exception review note"
    if RedisWorkerOversightSummary.ESCALATION_REVIEW_ARTIFACT in oversight_types:
        records[4].detail = "worker placeholder would emit a governance exception artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerInterventionDecision(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        decision_ready=True,
        metadata={
            "source_identifiers": oversight.metadata.get("source_identifiers"),
            "correlation_lineage": oversight.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
