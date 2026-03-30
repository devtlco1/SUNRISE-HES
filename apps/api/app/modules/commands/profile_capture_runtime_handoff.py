from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.commands.enums import (
    CommandCategory,
    CommandExecutionAttemptStatus,
    CommandPriority,
    CommandStatus,
)
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.schemas import (
    ProfileCaptureRuntimeHandoffRequest,
    ProfileCaptureRuntimeHandoffResponse,
    ProfileCaptureRuntimeHandoffResult,
)
from app.modules.commands.service import (
    _load_profile_capture_attempt_bootstrap,
    _validate_capture_load_profile_normalized_payload,
    _validate_profile_capture_endpoint_assignment,
    _validate_profile_capture_protocol_profile,
    get_meter_command,
    serialize_command_attempt,
    serialize_meter_command,
)
from app.modules.jobs.enums import JobCategory, JobRunStatus, JobScheduleType, JobTargetType
from app.modules.jobs.models import JobDefinition, JobRun
from app.modules.jobs.service import serialize_job_run
from app.runtime.contracts import (
    RuntimeExecutionHandoffLineage,
    RuntimeExecutionHandoffResult,
    RuntimeExecutionHandoffStatus,
    RuntimeProfileReadExecutionResult,
    RuntimeExecutionSessionResult,
    RuntimeExecutionSessionStatus,
)
from app.runtime.schemas import (
    RuntimeAttemptDispositionBridgeRequest,
    RuntimeClosureAttestationBridgeRequest,
    RuntimeDeliveryContractBridgeRequest,
    RuntimeDispatchEnvelopeBridgeRequest,
    RuntimeExecutionInvocationGateRequest,
    RuntimeExecutionLeaseRequest,
    RuntimeExecutionOutcomeCheckpointRequest,
    RuntimeExecutionSessionFinalizeRequest,
    RuntimeExecutionSessionStartRequest,
    RuntimeExternalizationEnvelopeBridgeRequest,
    RuntimeFollowUpMaterializationBridgeRequest,
    RuntimeOperationalClosureBridgeRequest,
    RuntimePostProcessingBridgeRequest,
    RuntimeProfileReadExecutionRequest,
    RuntimeProtocolAdapterSelectionBridgeRequest,
    RuntimeProtocolDispatchRequestBridgeRequest,
    RuntimeProtocolExecutionIntentBridgeRequest,
    RuntimeProtocolExecutionObservationBridgeRequest,
    RuntimeProtocolInterpretationBridgeRequest,
    RuntimeProtocolInvocationResultBridgeRequest,
    RuntimeProtocolReconciliationBridgeRequest,
    RuntimePublicationContractBridgeRequest,
    RuntimeTerminalSettlementBridgeRequest,
)
from app.runtime.services import (
    bridge_runtime_closure_attestation_to_publication_contract,
    bridge_runtime_delivery_contract_to_dispatch_envelope,
    bridge_runtime_disposition_to_post_processing,
    bridge_runtime_execution_outcome_to_attempt_disposition,
    bridge_runtime_externalization_envelope_to_delivery_contract,
    bridge_runtime_follow_up_materialization_to_operational_closure,
    bridge_runtime_operational_closure_to_protocol_execution_intent,
    bridge_runtime_post_processing_to_follow_up_materialization,
    bridge_runtime_protocol_adapter_selection_to_dispatch_request,
    bridge_runtime_protocol_dispatch_request_to_invocation_result,
    bridge_runtime_protocol_execution_intent_to_adapter_selection,
    bridge_runtime_protocol_execution_observation_to_interpretation,
    bridge_runtime_protocol_interpretation_to_reconciliation,
    bridge_runtime_protocol_invocation_result_to_execution_observation,
    bridge_runtime_protocol_reconciliation_to_terminal_settlement,
    bridge_runtime_publication_contract_to_externalization_envelope,
    bridge_runtime_terminal_settlement_to_closure_attestation,
    execute_runtime_profile_read_adapter,
    finalize_runtime_execution_session,
    gate_runtime_execution_invocation,
    lease_runtime_execution_work_item,
    record_runtime_execution_outcome,
    start_runtime_execution_session,
)
from app.runtime.services.runtime_artifact_utils import (
    load_runtime_execution_guard,
    merge_runtime_metadata,
)
from app.runtime.services.runtime_execution_guard import build_runtime_execution_guard_metadata

PROFILE_CAPTURE_RUNTIME_JOB_DEFINITION_CODE = "internal-profile-capture-runtime-handoff"
PROFILE_CAPTURE_RUNTIME_WORKER_PATH = "profile_capture_runtime_handoff"


def handoff_profile_capture_command_to_runtime(
    session: Session,
    *,
    command_id: uuid.UUID,
    payload: ProfileCaptureRuntimeHandoffRequest,
) -> ProfileCaptureRuntimeHandoffResponse:
    command = get_meter_command(session, command_id)
    latest_attempt = _load_latest_profile_capture_attempt(session, command_id=command.id)
    if latest_attempt is not None:
        existing_handoff = _load_profile_capture_runtime_handoff(latest_attempt.execution_metadata)
        existing_profile_read = _load_runtime_profile_read_execution(
            latest_attempt.execution_metadata
        )
        if existing_handoff is not None:
            if existing_handoff.get("handoff_identifier") != payload.handoff_identifier:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Profile-capture runtime handoff already exists for another handoff identifier.",
                )
            if existing_handoff.get("executor_identifier") != payload.executor_identifier:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Profile-capture runtime handoff is already owned by another executor.",
                )
            if existing_profile_read is not None:
                return _build_existing_profile_capture_runtime_handoff_response(
                    session,
                    attempt=latest_attempt,
                    command=command,
                    handoff_record=existing_handoff,
                )
    if command.command_template.category != CommandCategory.PROFILE_CAPTURE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the profile-capture runtime handoff slice.",
        )
    if command.current_status in {
        CommandStatus.SUCCEEDED,
        CommandStatus.FAILED,
        CommandStatus.CANCELLED,
        CommandStatus.TIMED_OUT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command is not runtime-handoff-eligible from its current state.",
        )

    normalized_payload = _validate_capture_load_profile_normalized_payload(command)
    assignment = _validate_profile_capture_endpoint_assignment(
        session,
        meter_id=command.meter_id,
        endpoint_assignment_id=command.endpoint_assignment_id,
    )
    _validate_profile_capture_protocol_profile(
        session,
        protocol_association_profile_id=command.protocol_association_profile_id,
    )
    attempt = _load_bootstrapped_profile_capture_attempt(session, command_id=command.id)
    bootstrap_record = _validate_bootstrapped_attempt_for_runtime_handoff(
        attempt=attempt,
        command=command,
        normalized_payload=normalized_payload,
        endpoint_id=assignment.endpoint_id,
    )
    existing_handoff = _load_profile_capture_runtime_handoff(attempt.execution_metadata)
    existing_profile_read = _load_runtime_profile_read_execution(attempt.execution_metadata)
    if existing_handoff is None and existing_profile_read is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt already has incompatible runtime execution state without a matching handoff artifact.",
        )

    job_run = _get_or_create_runtime_job_run(
        session,
        attempt=attempt,
        command=command,
        endpoint_id=assignment.endpoint_id,
        executor_identifier=payload.executor_identifier,
    )
    _persist_runtime_execution_handoff(
        session,
        attempt=attempt,
        command=command,
        job_run=job_run,
        executor_identifier=payload.executor_identifier,
        handoff_identifier=payload.handoff_identifier,
    )
    lease_runtime_execution_work_item(
        session,
        attempt_id=attempt.id,
        payload=RuntimeExecutionLeaseRequest(
            executor_identifier=payload.executor_identifier,
            lease_seconds=payload.lease_seconds,
        ),
    )
    gate_runtime_execution_invocation(
        session,
        attempt_id=attempt.id,
        payload=RuntimeExecutionInvocationGateRequest(
            executor_identifier=payload.executor_identifier,
        ),
    )
    _ensure_runtime_execution_guard(
        session,
        attempt_id=attempt.id,
        command_id=command.id,
        job_run_id=job_run.id,
        executor_identifier=payload.executor_identifier,
    )
    session_identifier = _get_or_finalize_runtime_execution_session(
        session,
        attempt_id=attempt.id,
        executor_identifier=payload.executor_identifier,
        session_timeout_seconds=payload.session_timeout_seconds,
        finalize_reason=payload.handoff_reason or "profile-capture-runtime-handoff",
    )
    record_runtime_execution_outcome(
        session,
        attempt_id=attempt.id,
        payload=RuntimeExecutionOutcomeCheckpointRequest(
            executor_identifier=payload.executor_identifier,
            session_identifier=session_identifier,
            terminal_outcome="completed",
            outcome_reason=payload.handoff_reason or "profile-capture-runtime-handoff",
            summary_message=(
                "Profile-capture runtime handoff advanced the bootstrapped attempt "
                "into the bounded runtime profile-read slice."
            ),
        ),
    )
    _bridge_profile_capture_runtime_chain(
        session,
        attempt_id=attempt.id,
        executor_identifier=payload.executor_identifier,
        session_identifier=session_identifier,
        handoff_reason=payload.handoff_reason,
    )
    profile_read_response = execute_runtime_profile_read_adapter(
        session,
        attempt_id=attempt.id,
        payload=RuntimeProfileReadExecutionRequest(
            executor_identifier=payload.executor_identifier,
            session_identifier=session_identifier,
            request_id=payload.handoff_identifier,
            execution_reason=payload.handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    refreshed_attempt = session.get(CommandExecutionAttempt, attempt.id)
    refreshed_command = session.get(MeterCommand, command.id)
    refreshed_job_run = session.get(JobRun, job_run.id)
    if refreshed_attempt is None or refreshed_command is None or refreshed_job_run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture runtime handoff could not load durable runtime state.",
        )
    profile_read_execution = _load_runtime_profile_read_execution(
        refreshed_attempt.execution_metadata
    )
    if profile_read_execution is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture runtime handoff did not record a runtime profile-read execution artifact.",
        )
    handoff_record = _build_profile_capture_runtime_handoff_record(
        attempt=refreshed_attempt,
        job_run=refreshed_job_run,
        bootstrap_record=bootstrap_record,
        payload=payload,
        session_identifier=session_identifier,
        profile_read_execution=profile_read_execution,
        reused_existing_handoff=existing_handoff is not None,
        reused_existing_runtime_execution=profile_read_response.result.already_recorded,
    )
    _persist_profile_capture_runtime_handoff_record(
        session,
        attempt=refreshed_attempt,
        command=refreshed_command,
        job_run=refreshed_job_run,
        handoff_record=handoff_record,
    )
    session.refresh(refreshed_attempt)
    session.refresh(refreshed_command)
    session.refresh(refreshed_job_run)
    return ProfileCaptureRuntimeHandoffResponse(
        result=ProfileCaptureRuntimeHandoffResult(
            handoff_status=str(handoff_record["handoff_status"]),
            command_id=refreshed_command.id,
            command_execution_attempt_id=refreshed_attempt.id,
            job_run_id=refreshed_job_run.id,
            handoff_identifier=str(handoff_record["handoff_identifier"]),
            executor_identifier=str(handoff_record["executor_identifier"]),
            bootstrap_identifier=str(handoff_record["bootstrap_identifier"]),
            handed_off_at=datetime.fromisoformat(str(handoff_record["handed_off_at"])),
            session_identifier=str(handoff_record["session_identifier"]),
            runtime_profile_read_execution_present=bool(
                handoff_record["runtime_profile_read_execution_present"]
            ),
            runtime_profile_read_execution_record_id=(
                str(handoff_record["runtime_profile_read_execution_record_id"])
                if handoff_record.get("runtime_profile_read_execution_record_id") is not None
                else None
            ),
            reused_existing_handoff=bool(handoff_record["reused_existing_handoff"]),
            reused_existing_runtime_execution=bool(
                handoff_record["reused_existing_runtime_execution"]
            ),
            handoff_record=handoff_record,
        ),
        job_run=serialize_job_run(refreshed_job_run).model_dump(mode="json"),
        related_command=serialize_meter_command(refreshed_command),
        created_or_existing_attempt=serialize_command_attempt(refreshed_attempt),
    )


def _load_bootstrapped_profile_capture_attempt(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandExecutionAttempt:
    attempt = session.scalar(
        select(CommandExecutionAttempt)
        .where(
            CommandExecutionAttempt.meter_command_id == command_id,
            CommandExecutionAttempt.ended_at.is_(None),
        )
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture command does not have a bootstrapped attempt for runtime handoff.",
        )
    return attempt


def _load_latest_profile_capture_attempt(
    session: Session,
    *,
    command_id: uuid.UUID,
) -> CommandExecutionAttempt | None:
    return session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command_id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )


def _build_existing_profile_capture_runtime_handoff_response(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    handoff_record: dict[str, object],
) -> ProfileCaptureRuntimeHandoffResponse:
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture runtime handoff artifact references a missing job run.",
        )
    job_run = session.get(JobRun, attempt.job_run_id)
    if job_run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture runtime handoff artifact references an unknown job run.",
        )
    return ProfileCaptureRuntimeHandoffResponse(
        result=ProfileCaptureRuntimeHandoffResult(
            handoff_status=str(handoff_record["handoff_status"]),
            command_id=command.id,
            command_execution_attempt_id=attempt.id,
            job_run_id=job_run.id,
            handoff_identifier=str(handoff_record["handoff_identifier"]),
            executor_identifier=str(handoff_record["executor_identifier"]),
            bootstrap_identifier=str(handoff_record["bootstrap_identifier"]),
            handed_off_at=datetime.fromisoformat(str(handoff_record["handed_off_at"])),
            session_identifier=str(handoff_record["session_identifier"]),
            runtime_profile_read_execution_present=bool(
                handoff_record["runtime_profile_read_execution_present"]
            ),
            runtime_profile_read_execution_record_id=(
                str(handoff_record["runtime_profile_read_execution_record_id"])
                if handoff_record.get("runtime_profile_read_execution_record_id") is not None
                else None
            ),
            reused_existing_handoff=True,
            reused_existing_runtime_execution=True,
            handoff_record=handoff_record,
        ),
        job_run=serialize_job_run(job_run).model_dump(mode="json"),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _validate_bootstrapped_attempt_for_runtime_handoff(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    normalized_payload: dict[str, object],
    endpoint_id: uuid.UUID,
) -> dict[str, object]:
    bootstrap_record = _load_profile_capture_attempt_bootstrap(attempt.execution_metadata)
    if bootstrap_record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt is missing the bootstrap artifact required for runtime handoff.",
        )
    if attempt.status != CommandExecutionAttemptStatus.STARTED or attempt.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt is not runtime-handoff-eligible from its current state.",
        )
    if not isinstance(attempt.request_snapshot, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt is missing a request snapshot for runtime handoff.",
        )
    if attempt.request_snapshot != normalized_payload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt request snapshot is incompatible with the normalized payload for runtime handoff.",
        )
    if attempt.endpoint_id != endpoint_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt endpoint continuity is incompatible with runtime handoff.",
        )
    if str(bootstrap_record.get("command_id")) != str(command.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt bootstrap artifact is incompatible with the selected command.",
        )
    if str(bootstrap_record.get("profile_read_operation")) != "capture_load_profile":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture attempt bootstrap artifact is incompatible with the capture-load-profile runtime slice.",
        )
    return bootstrap_record


def _get_or_create_runtime_job_definition(session: Session) -> JobDefinition:
    job_definition = session.scalar(
        select(JobDefinition).where(
            func.lower(JobDefinition.code) == PROFILE_CAPTURE_RUNTIME_JOB_DEFINITION_CODE
        )
    )
    if job_definition is not None:
        if job_definition.category != JobCategory.COMMAND:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existing internal profile-capture runtime job definition is incompatible.",
            )
        return job_definition
    job_definition = JobDefinition(
        code=PROFILE_CAPTURE_RUNTIME_JOB_DEFINITION_CODE,
        name="Internal Profile Capture Runtime Handoff",
        category=JobCategory.COMMAND,
        target_type=JobTargetType.METER,
        schedule_type=JobScheduleType.MANUAL,
        command_template_id=None,
        priority=CommandPriority.NORMAL,
        timeout_seconds=300,
        max_retries=0,
        is_active=True,
        notes="Internal bounded job definition for profile-capture command-to-runtime handoff.",
    )
    session.add(job_definition)
    session.flush()
    return job_definition


def _get_or_create_runtime_job_run(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    endpoint_id: uuid.UUID,
    executor_identifier: str,
) -> JobRun:
    if attempt.job_run_id is not None:
        job_run = session.get(JobRun, attempt.job_run_id)
        if job_run is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile-capture attempt references a missing job run for runtime handoff.",
            )
        if job_run.related_command_id != command.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile-capture attempt references an incompatible job run for runtime handoff.",
            )
        if job_run.target_endpoint_id != endpoint_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile-capture runtime handoff detected inconsistent endpoint continuity on the existing job run.",
            )
        return job_run

    now = datetime.now(UTC)
    job_definition = _get_or_create_runtime_job_definition(session)
    job_run = JobRun(
        job_definition_id=job_definition.id,
        target_meter_id=command.meter_id,
        target_endpoint_id=endpoint_id,
        related_command_id=command.id,
        scheduled_for=command.requested_at or now,
        available_at=command.requested_at or now,
        claimed_at=now,
        claim_expires_at=None,
        worker_identifier=executor_identifier,
        status=JobRunStatus.RUNNING,
        correlation_id=command.correlation_id,
        started_at=now,
        retry_count=0,
        max_retries=0,
        request_payload=attempt.request_snapshot or command.normalized_payload,
        result_summary=command.result_summary or {},
    )
    session.add(job_run)
    session.flush()
    attempt.job_run_id = job_run.id
    session.add_all([job_run, attempt])
    session.commit()
    session.refresh(job_run)
    session.refresh(attempt)
    return job_run


def _persist_runtime_execution_handoff(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun,
    executor_identifier: str,
    handoff_identifier: str,
) -> None:
    existing = _load_runtime_execution_handoff(job_run.result_summary)
    if existing is not None:
        if existing.worker_identifier != executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile-capture runtime handoff is already owned by another executor.",
            )
        return

    handed_off_at = datetime.now(UTC).isoformat()
    dispatch_request_identity = f"{job_run.id}:{handoff_identifier}"
    result = RuntimeExecutionHandoffResult(
        status=RuntimeExecutionHandoffStatus.HANDED_OFF,
        backend_name="command_service",
        handoff_record_id=f"profile-capture-runtime-handoff:{attempt.id}",
        stream_name="profile-capture-runtime-handoff",
        consumer_group="profile-capture-runtime-handoff",
        consumer_name=f"profile-capture-runtime:{executor_identifier}",
        worker_identifier=executor_identifier,
        job_run_id=str(job_run.id),
        related_command_id=str(command.id),
        command_attempt_id=str(attempt.id),
        handed_off_at=handed_off_at,
        job_run_claimed=False,
        command_materialized=False,
        attempt_started=False,
        summary=(
            "Profile-capture command runtime handoff linked the bootstrapped attempt "
            "to the bounded runtime execution chain."
        ),
        lineage=RuntimeExecutionHandoffLineage(
            dispatch_request_identity=dispatch_request_identity,
            queue_message_id=f"profile-capture-runtime-handoff-message:{attempt.id}",
            claim_token=f"profile-capture-runtime-handoff-claim:{handoff_identifier}",
            source_identifiers={
                "job_run_id": str(job_run.id),
                "command_id": str(command.id),
                "attempt_id": str(attempt.id),
            },
            correlation_lineage={
                "source_correlation_id": command.correlation_id,
                "derived_correlation_id": command.correlation_id,
            },
            dispatch_metadata={
                "synthetic": True,
                "source": "profile_capture_command_runtime_handoff",
                "handoff_identifier": handoff_identifier,
            },
            intended_worker_path=PROFILE_CAPTURE_RUNTIME_WORKER_PATH,
        ),
    )
    handoff_payload = result.model_dump(mode="json")
    attempt.execution_metadata = merge_runtime_metadata(
        attempt.execution_metadata,
        {
            "queue_runtime_handoff": handoff_payload,
        },
    )
    command.result_summary = merge_runtime_metadata(
        command.result_summary,
        {"runtime_execution_handoff": handoff_payload},
    )
    job_run.result_summary = merge_runtime_metadata(
        job_run.result_summary,
        {"runtime_execution_handoff": handoff_payload},
    )
    session.add_all([attempt, command, job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(command)
    session.refresh(job_run)


def _ensure_runtime_execution_guard(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    command_id: uuid.UUID,
    job_run_id: uuid.UUID,
    executor_identifier: str,
) -> None:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    command = session.get(MeterCommand, command_id)
    job_run = session.get(JobRun, job_run_id)
    if attempt is None or command is None or job_run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile-capture runtime handoff could not load durable runtime guard state.",
        )
    current_guard = load_runtime_execution_guard(attempt.execution_metadata)
    lease_payload = (
        attempt.execution_metadata.get("runtime_execution_lease")
        if isinstance(attempt.execution_metadata, dict)
        else None
    )
    invocation_payload = (
        attempt.execution_metadata.get("runtime_execution_invocation_gate")
        if isinstance(attempt.execution_metadata, dict)
        else None
    )
    if (
        current_guard is not None
        and isinstance(lease_payload, dict)
        and isinstance(invocation_payload, dict)
        and current_guard.executor_identifier == executor_identifier
        and current_guard.lease_record_id == lease_payload.get("lease_record_id")
        and current_guard.invocation_record_id == invocation_payload.get("invocation_record_id")
    ):
        return
    guard_metadata = build_runtime_execution_guard_metadata(
        execution_metadata=attempt.execution_metadata,
        executor_identifier=executor_identifier,
        attempt_id=str(attempt.id),
    )
    attempt.execution_metadata = merge_runtime_metadata(
        attempt.execution_metadata,
        guard_metadata,
    )
    command.result_summary = merge_runtime_metadata(command.result_summary, guard_metadata)
    job_run.result_summary = merge_runtime_metadata(job_run.result_summary, guard_metadata)
    session.add_all([attempt, command, job_run])
    session.commit()


def _get_or_finalize_runtime_execution_session(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    executor_identifier: str,
    session_timeout_seconds: int,
    finalize_reason: str,
) -> str:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command execution attempt not found.",
        )
    existing_session = _load_runtime_execution_session(attempt.execution_metadata)
    if existing_session is not None:
        if existing_session.executor_identifier != executor_identifier:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime execution session is already owned by another executor.",
            )
        if existing_session.status == RuntimeExecutionSessionStatus.FINALIZED:
            return existing_session.session_identifier
    session_result = start_runtime_execution_session(
        session,
        attempt_id=attempt_id,
        payload=RuntimeExecutionSessionStartRequest(
            executor_identifier=executor_identifier,
            session_timeout_seconds=session_timeout_seconds,
        ),
    )
    finalize_runtime_execution_session(
        session,
        attempt_id=attempt_id,
        payload=RuntimeExecutionSessionFinalizeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_result.result.session_identifier,
            finalize_reason=finalize_reason,
        ),
    )
    return session_result.result.session_identifier


def _bridge_profile_capture_runtime_chain(
    session: Session,
    *,
    attempt_id: uuid.UUID,
    executor_identifier: str,
    session_identifier: str,
    handoff_reason: str | None,
) -> None:
    bridge_runtime_execution_outcome_to_attempt_disposition(
        session,
        attempt_id=attempt_id,
        payload=RuntimeAttemptDispositionBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            disposition_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_disposition_to_post_processing(
        session,
        attempt_id=attempt_id,
        payload=RuntimePostProcessingBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            post_processing_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_post_processing_to_follow_up_materialization(
        session,
        attempt_id=attempt_id,
        payload=RuntimeFollowUpMaterializationBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            materialization_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_follow_up_materialization_to_operational_closure(
        session,
        attempt_id=attempt_id,
        payload=RuntimeOperationalClosureBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            closure_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_operational_closure_to_protocol_execution_intent(
        session,
        attempt_id=attempt_id,
        payload=RuntimeProtocolExecutionIntentBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            intent_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_protocol_execution_intent_to_adapter_selection(
        session,
        attempt_id=attempt_id,
        payload=RuntimeProtocolAdapterSelectionBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            selection_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_protocol_adapter_selection_to_dispatch_request(
        session,
        attempt_id=attempt_id,
        payload=RuntimeProtocolDispatchRequestBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            request_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_protocol_dispatch_request_to_invocation_result(
        session,
        attempt_id=attempt_id,
        payload=RuntimeProtocolInvocationResultBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            result_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_protocol_invocation_result_to_execution_observation(
        session,
        attempt_id=attempt_id,
        payload=RuntimeProtocolExecutionObservationBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            observation_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_protocol_execution_observation_to_interpretation(
        session,
        attempt_id=attempt_id,
        payload=RuntimeProtocolInterpretationBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            interpretation_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_protocol_interpretation_to_reconciliation(
        session,
        attempt_id=attempt_id,
        payload=RuntimeProtocolReconciliationBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            reconciliation_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_protocol_reconciliation_to_terminal_settlement(
        session,
        attempt_id=attempt_id,
        payload=RuntimeTerminalSettlementBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            settlement_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_terminal_settlement_to_closure_attestation(
        session,
        attempt_id=attempt_id,
        payload=RuntimeClosureAttestationBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            attestation_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_closure_attestation_to_publication_contract(
        session,
        attempt_id=attempt_id,
        payload=RuntimePublicationContractBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            publication_contract_reason=handoff_reason
            or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_publication_contract_to_externalization_envelope(
        session,
        attempt_id=attempt_id,
        payload=RuntimeExternalizationEnvelopeBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            envelope_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_externalization_envelope_to_delivery_contract(
        session,
        attempt_id=attempt_id,
        payload=RuntimeDeliveryContractBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            delivery_contract_reason=handoff_reason
            or "profile-capture-runtime-handoff",
        ),
    )
    bridge_runtime_delivery_contract_to_dispatch_envelope(
        session,
        attempt_id=attempt_id,
        payload=RuntimeDispatchEnvelopeBridgeRequest(
            executor_identifier=executor_identifier,
            session_identifier=session_identifier,
            dispatch_envelope_reason=handoff_reason or "profile-capture-runtime-handoff",
        ),
    )


def _build_profile_capture_runtime_handoff_record(
    *,
    attempt: CommandExecutionAttempt,
    job_run: JobRun,
    bootstrap_record: dict[str, object],
    payload: ProfileCaptureRuntimeHandoffRequest,
    session_identifier: str,
    profile_read_execution: RuntimeProfileReadExecutionResult,
    reused_existing_handoff: bool,
    reused_existing_runtime_execution: bool,
) -> dict[str, object]:
    return {
        "handoff_status": "handed_off",
        "command_id": str(attempt.meter_command_id),
        "command_execution_attempt_id": str(attempt.id),
        "job_run_id": str(job_run.id),
        "handoff_identifier": payload.handoff_identifier,
        "executor_identifier": payload.executor_identifier,
        "bootstrap_identifier": str(bootstrap_record["bootstrap_identifier"]),
        "bootstrap_record": bootstrap_record,
        "runtime_profile_read_execution_present": True,
        "runtime_profile_read_execution_record_id": (
            profile_read_execution.profile_read_execution_record_id
        ),
        "reused_existing_handoff": reused_existing_handoff,
        "reused_existing_runtime_execution": reused_existing_runtime_execution,
        "session_identifier": session_identifier,
        "handed_off_at": datetime.now(UTC).isoformat(),
        "trace_references": {
            "dispatch_envelope_record_id": profile_read_execution.dispatch_envelope_record_id,
            "correlation_id": profile_read_execution.correlation_id,
            "request_id": profile_read_execution.request_id,
        },
    }


def _persist_profile_capture_runtime_handoff_record(
    session: Session,
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun,
    handoff_record: dict[str, object],
) -> None:
    payload = {"profile_capture_runtime_handoff": handoff_record}
    attempt.execution_metadata = merge_runtime_metadata(attempt.execution_metadata, payload)
    command.result_summary = merge_runtime_metadata(command.result_summary, payload)
    job_run.result_summary = merge_runtime_metadata(job_run.result_summary, payload)
    session.add_all([attempt, command, job_run])
    session.commit()


def _load_profile_capture_runtime_handoff(
    execution_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("profile_capture_runtime_handoff")
    return payload if isinstance(payload, dict) else None


def _load_runtime_execution_handoff(
    result_summary: dict[str, object] | None,
) -> RuntimeExecutionHandoffResult | None:
    if not isinstance(result_summary, dict):
        return None
    payload = result_summary.get("runtime_execution_handoff")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionHandoffResult.model_validate(payload)


def _load_runtime_profile_read_execution(
    execution_metadata: dict[str, object] | None,
) -> RuntimeProfileReadExecutionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_profile_read_execution")
    if not isinstance(payload, dict):
        return None
    return RuntimeProfileReadExecutionResult.model_validate(payload)


def _load_runtime_execution_session(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionSessionResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_session")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionSessionResult.model_validate(payload)
