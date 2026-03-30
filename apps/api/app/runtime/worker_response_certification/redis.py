from __future__ import annotations

from app.runtime.contracts import (
    RedisWorkerAssuranceArtifact,
    RedisWorkerCertificationArtifact,
    RedisWorkerResponseAssuranceSummary,
    RedisWorkerResponseCertificationRecord,
    RedisWorkerResponseCertificationSummary,
)


def map_worker_response_assurance_to_response_certification(
    response_assurance: RedisWorkerAssuranceArtifact,
) -> RedisWorkerCertificationArtifact:
    redelivery_decision = str(
        response_assurance.metadata.get("redelivery_decision", "retain_for_retry")
    )
    assurance_types = {record.assurance_type for record in response_assurance.records}

    records = [
        RedisWorkerResponseCertificationRecord(
            certification_type=RedisWorkerResponseCertificationSummary.NOOP_RESPONSE_CERTIFICATION,
            detail="worker placeholder kept response-certification generation unchanged for inspection",
            terminal=False,
        ),
        RedisWorkerResponseCertificationRecord(
            certification_type=RedisWorkerResponseCertificationSummary.RESPONSE_CERTIFICATION_SUMMARY,
            detail="worker placeholder reserved response-certification summary artifact",
            terminal=True,
        ),
        RedisWorkerResponseCertificationRecord(
            certification_type=RedisWorkerResponseCertificationSummary.CERTIFICATION_ACTION_RECORD,
            detail=f"worker placeholder certification action follows redelivery decision: {redelivery_decision}",
            terminal=True,
        ),
        RedisWorkerResponseCertificationRecord(
            certification_type=RedisWorkerResponseCertificationSummary.CERTIFICATION_NOTE,
            detail="worker placeholder reserved certification note",
            terminal=True,
        ),
        RedisWorkerResponseCertificationRecord(
            certification_type=RedisWorkerResponseCertificationSummary.COMPLETION_CERTIFICATION_ARTIFACT,
            detail="worker placeholder reserved completion certification artifact",
            terminal=True,
        ),
    ]

    if RedisWorkerResponseAssuranceSummary.RESPONSE_ASSURANCE_SUMMARY in assurance_types:
        records[1].detail = "worker placeholder would emit a response-certification summary"
    if RedisWorkerResponseAssuranceSummary.ASSURANCE_ACTION_RECORD in assurance_types:
        records[2].detail = (
            f"worker placeholder would emit a certification-action record for {redelivery_decision}"
        )
    if RedisWorkerResponseAssuranceSummary.ASSURANCE_NOTE in assurance_types:
        records[3].detail = "worker placeholder would emit a certification note"
    if RedisWorkerResponseAssuranceSummary.POST_VERIFICATION_ARTIFACT in assurance_types:
        records[4].detail = "worker placeholder would emit a completion certification artifact"

    terminal_records = sum(1 for record in records if record.terminal)
    return RedisWorkerCertificationArtifact(
        records=records,
        total_records=len(records),
        terminal_records=terminal_records,
        certification_ready=True,
        metadata={
            "source_identifiers": response_assurance.metadata.get("source_identifiers"),
            "correlation_lineage": response_assurance.metadata.get("correlation_lineage"),
            "redelivery_decision": redelivery_decision,
        },
    )
