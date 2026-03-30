from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerExceptionGovernanceSummary,
    RedisWorkerInterventionDecision,
    RedisWorkerRemediationRecord,
    RedisWorkerRemediationSummary,
    RedisWorkerResponseArtifact,
)


def map_worker_exception_governance_to_remediation(
    exception_governance: RedisWorkerInterventionDecision,
) -> RedisWorkerResponseArtifact:
    redelivery_decision = str(
        exception_governance.metadata.get("redelivery_decision", "retain_for_retry")
    )
    governance_types = {record.governance_type for record in exception_governance.records}

    records = [
        RedisWorkerRemediationRecord(
            remediation_type=RedisWorkerRemediationSummary.NOOP_REMEDIATION,
            detail="worker placeholder kept remediation generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerRemediationRecord(
            remediation_type=RedisWorkerRemediationSummary.REMEDIATION_SUMMARY,
            detail="worker placeholder reserved remediation summary artifact",
            terminal=True,
        ),
        RedisWorkerRemediationRecord(
            remediation_type=RedisWorkerRemediationSummary.RESPONSE_ACTION_RECORD,
            detail=f"worker placeholder response action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerRemediationRecord(
            remediation_type=RedisWorkerRemediationSummary.REMEDIATION_NOTE,
            detail="worker placeholder reserved remediation note",
            terminal=True,
        ),
        RedisWorkerRemediationRecord(
            remediation_type=RedisWorkerRemediationSummary.EXCEPTION_RESPONSE_ARTIFACT,
            detail="worker placeholder reserved exception response artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerExceptionGovernanceSummary.EXCEPTION_GOVERNANCE_SUMMARY in governance_types:
        records[1].detail = "worker placeholder would emit a remediation summary"
    if RedisWorkerExceptionGovernanceSummary.INTERVENTION_DECISION_RECORD in governance_types:
        records[2].detail = (
            f"worker placeholder would emit a response-action record for {redelivery_decision}"
        )
    if RedisWorkerExceptionGovernanceSummary.EXCEPTION_REVIEW_NOTE in governance_types:
        records[3].detail = "worker placeholder would emit a remediation note"
    if RedisWorkerExceptionGovernanceSummary.GOVERNANCE_EXCEPTION_ARTIFACT in governance_types:
        records[4].detail = "worker placeholder would emit an exception response artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerResponseArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        response_ready=True,
        metadata={
            "source_identifiers": exception_governance.metadata.get("source_identifiers"),
            "correlation_lineage": exception_governance.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
