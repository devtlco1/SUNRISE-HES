from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerAuditLedger,
    RedisWorkerGovernanceRecord,
    RedisWorkerGovernanceSummary,
    RedisWorkerPolicyReview,
    RedisWorkerVerificationRecord,
)


def map_worker_audit_ledger_to_governance(
    ledger: RedisWorkerVerificationRecord,
) -> RedisWorkerPolicyReview:
    redelivery_decision = str(ledger.metadata.get("redelivery_decision", "retain_for_retry"))
    entry_types = {entry.entry_type for entry in ledger.ledger_entries}

    records = [
        RedisWorkerGovernanceRecord(
            governance_type=RedisWorkerGovernanceSummary.NOOP_GOVERNANCE,
            detail="worker placeholder kept governance generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerGovernanceRecord(
            governance_type=RedisWorkerGovernanceSummary.GOVERNANCE_SUMMARY,
            detail="worker placeholder reserved governance summary artifact",
            terminal=True,
        ),
        RedisWorkerGovernanceRecord(
            governance_type=RedisWorkerGovernanceSummary.POLICY_REVIEW_RECORD,
            detail=f"worker placeholder policy review follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerGovernanceRecord(
            governance_type=RedisWorkerGovernanceSummary.COMPLIANCE_CONTROL_SUMMARY,
            detail="worker placeholder reserved compliance-control summary artifact",
            terminal=True,
        ),
        RedisWorkerGovernanceRecord(
            governance_type=RedisWorkerGovernanceSummary.OPERATIONAL_GOVERNANCE_NOTE,
            detail="worker placeholder reserved operational governance note",
            terminal=True,
        ),
    ]

    if RedisWorkerAuditLedger.AUDIT_LEDGER_ENTRY in entry_types:
        records[1].detail = "worker placeholder would emit a governance summary"
    if RedisWorkerAuditLedger.VERIFICATION_RECORD in entry_types:
        records[2].detail = (
            f"worker placeholder would emit a policy review record for {redelivery_decision}"
        )
    if RedisWorkerAuditLedger.COMPLIANCE_READY_ENTRY in entry_types:
        records[3].detail = "worker placeholder would emit a compliance-control summary"
    if RedisWorkerAuditLedger.RECONCILIATION_HISTORY_ENTRY in entry_types:
        records[4].detail = "worker placeholder would emit an operational governance note"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerPolicyReview(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        review_ready=True,
        metadata={
            "source_identifiers": ledger.metadata.get("source_identifiers"),
            "correlation_lineage": ledger.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
