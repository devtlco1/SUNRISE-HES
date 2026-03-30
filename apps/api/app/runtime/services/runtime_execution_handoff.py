from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.service import serialize_command_attempt, serialize_meter_command
from app.modules.jobs.models import JobRun
from app.modules.jobs.schemas import (
    PrepareJobRunForExecutionRequest,
    PrepareJobRunForExecutionResponse,
)
from app.modules.jobs.service import get_job_run, prepare_job_run_for_execution, serialize_job_run
from app.runtime.contracts import (
    RuntimeExecutionHandoffLineage,
    RuntimeExecutionHandoffResult,
    RuntimeExecutionHandoffStatus,
)
from app.runtime.redis_dispatch_stream import parse_dispatch_stream_message
from app.runtime.schemas import (
    RedisDispatchRuntimeHandoffRequest,
    RuntimeExecutionHandoffResponse,
)
from app.runtime.services.redis_queue_claim_state import load_pending_redis_dispatch_claim


def handoff_claimed_redis_dispatch_message_to_runtime(
    session: Session,
    *,
    payload: RedisDispatchRuntimeHandoffRequest,
) -> RuntimeExecutionHandoffResponse:
    claim = load_pending_redis_dispatch_claim(
        worker_identifier=payload.worker_identifier,
        message_id=payload.message_id,
        claim_token=payload.claim_token,
        include_fields=True,
    )
    handed_off_at = datetime.now(UTC)
    message = parse_dispatch_stream_message(
        message_id=payload.message_id,
        fields=claim["fields"],
        claimed_at=handed_off_at.isoformat(),
        delivery_count=int(claim["pending_entry"].get("times_delivered", 1)),
    )
    job_run_id = _resolve_job_run_id(message.source_identifiers, message.body)
    job_run = get_job_run(session, uuid.UUID(job_run_id))
    _validate_dispatch_identity(
        job_run=job_run,
        dispatch_request_identity=message.dispatch_request_identity,
    )

    existing = _load_existing_runtime_handoff(job_run.result_summary)
    if existing is not None and _handoff_matches_existing_record(
        existing=existing,
        worker_identifier=payload.worker_identifier,
        message_id=payload.message_id,
        dispatch_request_identity=message.dispatch_request_identity,
    ):
        existing_attempt = _load_attempt(session, existing.command_attempt_id)
        existing_command = _load_command(session, existing.related_command_id)
        if existing_attempt is not None and existing_command is not None:
            return RuntimeExecutionHandoffResponse(
                result=existing,
                job_run=serialize_job_run(job_run),
                related_command=serialize_meter_command(existing_command),
                created_or_existing_attempt=serialize_command_attempt(existing_attempt),
            )

    handoff_metadata = _build_attempt_handoff_metadata(
        payload=payload,
        message=message,
        claim=claim,
        handed_off_at=handed_off_at.isoformat(),
    )
    prepared = prepare_job_run_for_execution(
        session,
        job_run_id=uuid.UUID(job_run_id),
        payload=PrepareJobRunForExecutionRequest(
            worker_identifier=payload.worker_identifier,
            lease_seconds=payload.lease_seconds,
            endpoint_id=payload.endpoint_id,
            session_history_id=payload.session_history_id,
            request_snapshot=payload.request_snapshot,
            execution_metadata=_merge_dicts(payload.execution_metadata, handoff_metadata),
        ),
    )
    attempt = session.get(
        CommandExecutionAttempt,
        prepared.created_or_existing_attempt.id,
    )
    command = session.get(MeterCommand, prepared.related_command.id)
    refreshed_job_run = session.get(JobRun, uuid.UUID(job_run_id))
    if attempt is None or command is None or refreshed_job_run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution handoff could not load durable runtime state.",
        )

    result = _build_runtime_handoff_result(
        payload=payload,
        message=message,
        claim=claim,
        handed_off_at=handed_off_at.isoformat(),
        prepared=prepared,
    )
    attempt.execution_metadata = _merge_dicts(
        attempt.execution_metadata,
        _merge_dicts(
            handoff_metadata,
            {"runtime_execution_handoff": result.model_dump(mode="json")},
        ),
    )
    command.result_summary = _merge_dicts(
        command.result_summary,
        {"runtime_execution_handoff": result.model_dump(mode="json")},
    )
    refreshed_job_run.result_summary = _merge_dicts(
        refreshed_job_run.result_summary,
        {"runtime_execution_handoff": result.model_dump(mode="json")},
    )
    session.add_all([attempt, command, refreshed_job_run])
    session.commit()
    session.refresh(attempt)
    session.refresh(refreshed_job_run)
    return RuntimeExecutionHandoffResponse(
        result=result,
        job_run=serialize_job_run(refreshed_job_run),
        related_command=serialize_meter_command(command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
    )


def _resolve_job_run_id(
    source_identifiers: dict[str, str | None],
    body: dict[str, object],
) -> str:
    job_run_id = source_identifiers.get("job_run_id")
    if job_run_id is None:
        source = body.get("source")
        if isinstance(source, dict):
            source_job_run_id = source.get("job_run_id")
            if isinstance(source_job_run_id, str):
                job_run_id = source_job_run_id
    if not isinstance(job_run_id, str):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message does not include a valid source job run id.",
        )
    try:
        uuid.UUID(job_run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message source job run id is invalid.",
        ) from exc
    return job_run_id


def _validate_dispatch_identity(*, job_run: JobRun, dispatch_request_identity: str) -> None:
    if not dispatch_request_identity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message does not include a dispatch identity.",
        )
    if not dispatch_request_identity.startswith(f"{job_run.id}:"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message does not match the source job run lineage.",
        )


def _load_existing_runtime_handoff(
    result_summary: dict[str, object] | None,
) -> RuntimeExecutionHandoffResult | None:
    if not isinstance(result_summary, dict):
        return None
    payload = result_summary.get("runtime_execution_handoff")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionHandoffResult.model_validate(payload)


def _handoff_matches_existing_record(
    *,
    existing: RuntimeExecutionHandoffResult,
    worker_identifier: str,
    message_id: str,
    dispatch_request_identity: str,
) -> bool:
    return (
        existing.worker_identifier == worker_identifier
        and existing.lineage.queue_message_id == message_id
        and existing.lineage.dispatch_request_identity == dispatch_request_identity
    )


def _build_attempt_handoff_metadata(
    *,
    payload: RedisDispatchRuntimeHandoffRequest,
    message,
    claim: dict[str, object],
    handed_off_at: str,
) -> dict[str, object]:
    return {
        "queue_runtime_handoff": {
            "backend_name": "redis",
            "stream_name": claim["stream_name"],
            "consumer_group": claim["consumer_group"],
            "consumer_name": claim["consumer_name"],
            "worker_identifier": payload.worker_identifier,
            "message_id": payload.message_id,
            "claim_token": payload.claim_token,
            "dispatch_request_identity": message.dispatch_request_identity,
            "source_identifiers": message.source_identifiers,
            "correlation_lineage": message.correlation_lineage,
            "dispatch_metadata": message.dispatch_metadata,
            "intended_worker_path": message.intended_worker_path,
            "handed_off_at": handed_off_at,
        }
    }


def _build_runtime_handoff_result(
    *,
    payload: RedisDispatchRuntimeHandoffRequest,
    message,
    claim: dict[str, object],
    handed_off_at: str,
    prepared: PrepareJobRunForExecutionResponse,
) -> RuntimeExecutionHandoffResult:
    return RuntimeExecutionHandoffResult(
        status=RuntimeExecutionHandoffStatus.HANDED_OFF,
        handoff_record_id=f"redis-runtime-handoff:{payload.message_id}",
        stream_name=str(claim["stream_name"]),
        consumer_group=str(claim["consumer_group"]),
        consumer_name=str(claim["consumer_name"]),
        worker_identifier=payload.worker_identifier,
        job_run_id=str(prepared.job_run.id),
        related_command_id=str(prepared.related_command.id),
        command_attempt_id=str(prepared.created_or_existing_attempt.id),
        handed_off_at=handed_off_at,
        job_run_claimed=prepared.job_run_claimed,
        command_materialized=prepared.command_materialized,
        attempt_started=prepared.attempt_started,
        summary=(
            "Runtime execution handoff is registered and durable work is ready "
            "without starting live protocol execution."
        ),
        lineage=RuntimeExecutionHandoffLineage(
            dispatch_request_identity=message.dispatch_request_identity,
            queue_message_id=payload.message_id,
            claim_token=payload.claim_token,
            source_identifiers={
                key: value if isinstance(value, str) or value is None else str(value)
                for key, value in message.source_identifiers.items()
            },
            correlation_lineage={
                key: value if isinstance(value, str) or value is None else str(value)
                for key, value in message.correlation_lineage.items()
            },
            dispatch_metadata=message.dispatch_metadata,
            intended_worker_path=message.intended_worker_path,
        ),
    )


def _merge_dicts(
    existing: dict[str, object] | None,
    extra: dict[str, object] | None,
) -> dict[str, object]:
    merged: dict[str, object] = {}
    if isinstance(existing, dict):
        merged.update(existing)
    if isinstance(extra, dict):
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}  # type: ignore[index]
            else:
                merged[key] = value
    return merged


def _load_attempt(session: Session, attempt_id: str | None) -> CommandExecutionAttempt | None:
    if attempt_id is None:
        return None
    return session.get(CommandExecutionAttempt, uuid.UUID(attempt_id))


def _load_command(session: Session, command_id: str | None) -> MeterCommand | None:
    if command_id is None:
        return None
    return session.get(MeterCommand, uuid.UUID(command_id))
