from __future__ import annotations

from app.runtime.broker_lifecycle import map_redis_semantics_to_lifecycle_contracts
from app.runtime.broker_semantics import map_envelope_to_redis_semantics
from app.runtime.contracts import (
    DerivedWorkDispatchCategory,
    DerivedWorkEnqueueCategory,
    QueueEnqueuePayload,
    QueueEnqueueResult,
    QueueEnqueueStatus,
)
from app.runtime.queue_serializers import RedisPlaceholderQueueSerializer
from app.runtime.worker_attestation_closure import (
    map_worker_settlement_attestation_to_attestation_closure,
)
from app.runtime.worker_attestation_seal import (
    map_worker_completion_attestation_to_attestation_seal,
)
from app.runtime.worker_audit_ledger import map_worker_reconciliation_to_audit_ledger
from app.runtime.worker_closure_archive import (
    map_worker_ledger_closure_to_closure_archive,
)
from app.runtime.worker_closure_reports import map_worker_finalization_to_closure_report
from app.runtime.worker_completion_attestation import (
    map_worker_response_certification_to_completion_attestation,
)
from app.runtime.worker_consumption import map_lifecycle_to_worker_consumption
from app.runtime.worker_control_plane import map_worker_governance_to_control_plane
from app.runtime.worker_dispositions import map_worker_resolution_to_disposition_timeline
from app.runtime.worker_exception_governance import (
    map_worker_oversight_to_exception_governance,
)
from app.runtime.worker_final_attestation_ledger import (
    map_worker_attestation_seal_to_final_attestation_ledger,
)
from app.runtime.worker_finalizations import map_worker_disposition_to_finalization_timeline
from app.runtime.worker_governance import map_worker_audit_ledger_to_governance
from app.runtime.worker_ledger_closure import (
    map_worker_final_attestation_ledger_to_ledger_closure,
)
from app.runtime.worker_outcomes import map_worker_progress_to_outcome_timeline
from app.runtime.worker_oversight import map_worker_control_plane_to_oversight
from app.runtime.worker_progress import map_worker_state_to_progress_timeline
from app.runtime.worker_reconciliation import map_worker_closure_report_to_reconciliation_snapshot
from app.runtime.worker_recovery_verification import (
    map_worker_remediation_to_recovery_verification,
)
from app.runtime.worker_register_closeout import (
    map_worker_register_reconciliation_to_register_closeout,
)
from app.runtime.worker_register_completion import (
    map_worker_register_publication_to_register_completion,
)
from app.runtime.worker_register_finalization import (
    map_worker_register_closeout_to_register_finalization,
)
from app.runtime.worker_register_publication import (
    map_worker_register_finalization_to_register_publication,
)
from app.runtime.worker_register_reconciliation import (
    map_worker_retention_register_to_register_reconciliation,
)
from app.runtime.worker_register_settlement import (
    map_worker_register_completion_to_register_settlement,
)
from app.runtime.worker_remediation import map_worker_exception_governance_to_remediation
from app.runtime.worker_resolutions import map_worker_outcome_to_resolution_timeline
from app.runtime.worker_response_assurance import (
    map_worker_recovery_verification_to_response_assurance,
)
from app.runtime.worker_response_certification import (
    map_worker_response_assurance_to_response_certification,
)
from app.runtime.worker_retention_register import (
    map_worker_closure_archive_to_retention_register,
)
from app.runtime.worker_settlement_attestation import (
    map_worker_register_settlement_to_settlement_attestation,
)
from app.runtime.worker_state import map_worker_consumption_to_state_timeline


class RedisPlaceholderQueueAdapter:
    def enqueue(self, payload: QueueEnqueuePayload) -> QueueEnqueueResult:
        serializer = RedisPlaceholderQueueSerializer()
        envelope = serializer.serialize(payload)
        semantics = map_envelope_to_redis_semantics(envelope)
        lifecycle = map_redis_semantics_to_lifecycle_contracts(semantics)
        worker_consumption = map_lifecycle_to_worker_consumption(lifecycle)
        worker_state = map_worker_consumption_to_state_timeline(worker_consumption)
        worker_progress = map_worker_state_to_progress_timeline(worker_state)
        worker_outcomes = map_worker_progress_to_outcome_timeline(worker_progress)
        worker_resolutions = map_worker_outcome_to_resolution_timeline(worker_outcomes)
        worker_dispositions = map_worker_resolution_to_disposition_timeline(worker_resolutions)
        worker_finalizations = map_worker_disposition_to_finalization_timeline(worker_dispositions)
        worker_closure_report = map_worker_finalization_to_closure_report(worker_finalizations)
        worker_reconciliation = map_worker_closure_report_to_reconciliation_snapshot(
            worker_closure_report
        )
        worker_audit_ledger = map_worker_reconciliation_to_audit_ledger(worker_reconciliation)
        worker_governance = map_worker_audit_ledger_to_governance(worker_audit_ledger)
        worker_control_plane = map_worker_governance_to_control_plane(worker_governance)
        worker_oversight = map_worker_control_plane_to_oversight(worker_control_plane)
        worker_exception_governance = map_worker_oversight_to_exception_governance(worker_oversight)
        worker_remediation = map_worker_exception_governance_to_remediation(
            worker_exception_governance
        )
        worker_recovery_verification = map_worker_remediation_to_recovery_verification(
            worker_remediation
        )
        worker_response_assurance = map_worker_recovery_verification_to_response_assurance(
            worker_recovery_verification
        )
        worker_response_certification = map_worker_response_assurance_to_response_certification(
            worker_response_assurance
        )
        worker_completion_attestation = map_worker_response_certification_to_completion_attestation(
            worker_response_certification
        )
        worker_attestation_seal = map_worker_completion_attestation_to_attestation_seal(
            worker_completion_attestation
        )
        worker_final_attestation_ledger = map_worker_attestation_seal_to_final_attestation_ledger(
            worker_attestation_seal
        )
        worker_ledger_closure = map_worker_final_attestation_ledger_to_ledger_closure(
            worker_final_attestation_ledger
        )
        worker_closure_archive = map_worker_ledger_closure_to_closure_archive(worker_ledger_closure)
        worker_retention_register = map_worker_closure_archive_to_retention_register(
            worker_closure_archive
        )
        worker_register_reconciliation = map_worker_retention_register_to_register_reconciliation(
            worker_retention_register
        )
        worker_register_closeout = map_worker_register_reconciliation_to_register_closeout(
            worker_register_reconciliation
        )
        worker_register_finalization = map_worker_register_closeout_to_register_finalization(
            worker_register_closeout
        )
        worker_register_publication = map_worker_register_finalization_to_register_publication(
            worker_register_finalization
        )
        worker_register_completion = map_worker_register_publication_to_register_completion(
            worker_register_publication
        )
        worker_register_settlement = map_worker_register_completion_to_register_settlement(
            worker_register_completion
        )
        worker_settlement_attestation = map_worker_register_settlement_to_settlement_attestation(
            worker_register_settlement
        )
        worker_attestation_closure = map_worker_settlement_attestation_to_attestation_closure(
            worker_settlement_attestation
        )
        return QueueEnqueueResult(
            enqueue_category=_map_dispatch_to_enqueue_category(payload.dispatch_category),
            dispatch_request_identity=f"{payload.source_job_run_id}:{payload.dispatch_category.value}",
            source_job_run_id=payload.source_job_run_id,
            lineage=payload.lineage,
            derived_correlation_id=payload.derived_correlation_id,
            adapter_receipt_id=semantics.receipt.receipt_id,
            enqueue_status=QueueEnqueueStatus.ACCEPTED,
            enqueue_metadata={
                "adapter": "redis_placeholder_queue_adapter",
                "payload_version": payload.payload_version.value,
                "serialized_payload": payload.serialized_payload,
                "backend_message_envelope": envelope.model_dump(mode="json"),
                "redis_semantics": semantics.model_dump(mode="json"),
                "redis_lifecycle": lifecycle.model_dump(mode="json"),
                "redis_worker_consumption": worker_consumption.model_dump(mode="json"),
                "redis_worker_state": worker_state.model_dump(mode="json"),
                "redis_worker_progress": worker_progress.model_dump(mode="json"),
                "redis_worker_outcomes": worker_outcomes.model_dump(mode="json"),
                "redis_worker_resolutions": worker_resolutions.model_dump(mode="json"),
                "redis_worker_dispositions": worker_dispositions.model_dump(mode="json"),
                "redis_worker_finalizations": worker_finalizations.model_dump(mode="json"),
                "redis_worker_closure_report": worker_closure_report.model_dump(mode="json"),
                "redis_worker_reconciliation": worker_reconciliation.model_dump(mode="json"),
                "redis_worker_audit_ledger": worker_audit_ledger.model_dump(mode="json"),
                "redis_worker_governance": worker_governance.model_dump(mode="json"),
                "redis_worker_control_plane": worker_control_plane.model_dump(mode="json"),
                "redis_worker_oversight": worker_oversight.model_dump(mode="json"),
                "redis_worker_exception_governance": (
                    worker_exception_governance.model_dump(mode="json")
                ),
                "redis_worker_remediation": worker_remediation.model_dump(mode="json"),
                "redis_worker_recovery_verification": (
                    worker_recovery_verification.model_dump(mode="json")
                ),
                "redis_worker_response_assurance": (
                    worker_response_assurance.model_dump(mode="json")
                ),
                "redis_worker_response_certification": (
                    worker_response_certification.model_dump(mode="json")
                ),
                "redis_worker_completion_attestation": (
                    worker_completion_attestation.model_dump(mode="json")
                ),
                "redis_worker_attestation_seal": worker_attestation_seal.model_dump(mode="json"),
                "redis_worker_final_attestation_ledger": (
                    worker_final_attestation_ledger.model_dump(mode="json")
                ),
                "redis_worker_ledger_closure": worker_ledger_closure.model_dump(mode="json"),
                "redis_worker_closure_archive": worker_closure_archive.model_dump(mode="json"),
                "redis_worker_retention_register": (
                    worker_retention_register.model_dump(mode="json")
                ),
                "redis_worker_register_reconciliation": (
                    worker_register_reconciliation.model_dump(mode="json")
                ),
                "redis_worker_register_closeout": worker_register_closeout.model_dump(mode="json"),
                "redis_worker_register_finalization": (
                    worker_register_finalization.model_dump(mode="json")
                ),
                "redis_worker_register_publication": (
                    worker_register_publication.model_dump(mode="json")
                ),
                "redis_worker_register_completion": (
                    worker_register_completion.model_dump(mode="json")
                ),
                "redis_worker_register_settlement": (
                    worker_register_settlement.model_dump(mode="json")
                ),
                "redis_worker_settlement_attestation": (
                    worker_settlement_attestation.model_dump(mode="json")
                ),
                "redis_worker_attestation_closure": (
                    worker_attestation_closure.model_dump(mode="json")
                ),
            },
            intended_path=payload.intended_worker_path,
        )


def _map_dispatch_to_enqueue_category(
    dispatch_category: DerivedWorkDispatchCategory,
) -> DerivedWorkEnqueueCategory:
    if dispatch_category == DerivedWorkDispatchCategory.RETRY_DISPATCH_REQUEST:
        return DerivedWorkEnqueueCategory.RETRY_ENQUEUE_RESULT
    return DerivedWorkEnqueueCategory.FOLLOWUP_ENQUEUE_RESULT
