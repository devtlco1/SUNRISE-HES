from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerApprovalArtifact,
    RedisWorkerControlPlaneRecord,
    RedisWorkerControlPlaneSummary,
    RedisWorkerGovernanceSummary,
    RedisWorkerPolicyReview,
)


def map_worker_governance_to_control_plane(
    governance: RedisWorkerPolicyReview,
) -> RedisWorkerApprovalArtifact:
    redelivery_decision = str(governance.metadata.get("redelivery_decision", "retain_for_retry"))
    governance_types = {record.governance_type for record in governance.records}

    records = [
        RedisWorkerControlPlaneRecord(
            control_type=RedisWorkerControlPlaneSummary.NOOP_CONTROL_PLANE,
            detail="worker placeholder kept control-plane generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerControlPlaneRecord(
            control_type=RedisWorkerControlPlaneSummary.CONTROL_PLANE_SUMMARY,
            detail="worker placeholder reserved control-plane summary artifact",
            terminal=True,
        ),
        RedisWorkerControlPlaneRecord(
            control_type=RedisWorkerControlPlaneSummary.APPROVAL_REQUIRED_RECORD,
            detail=f"worker placeholder approval flow follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerControlPlaneRecord(
            control_type=RedisWorkerControlPlaneSummary.BROKER_OPERATIONS_NOTE,
            detail="worker placeholder reserved broker operations note",
            terminal=True,
        ),
        RedisWorkerControlPlaneRecord(
            control_type=RedisWorkerControlPlaneSummary.CONTROL_REVIEW_ARTIFACT,
            detail="worker placeholder reserved control review artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerGovernanceSummary.GOVERNANCE_SUMMARY in governance_types:
        records[1].detail = "worker placeholder would emit a control-plane summary"
    if RedisWorkerGovernanceSummary.POLICY_REVIEW_RECORD in governance_types:
        records[2].detail = (
            f"worker placeholder would emit an approval-required record for {redelivery_decision}"
        )
    if RedisWorkerGovernanceSummary.OPERATIONAL_GOVERNANCE_NOTE in governance_types:
        records[3].detail = "worker placeholder would emit a broker operations note"
    if RedisWorkerGovernanceSummary.COMPLIANCE_CONTROL_SUMMARY in governance_types:
        records[4].detail = "worker placeholder would emit a control review artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerApprovalArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        approval_ready=True,
        metadata={
            "source_identifiers": governance.metadata.get("source_identifiers"),
            "correlation_lineage": governance.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
