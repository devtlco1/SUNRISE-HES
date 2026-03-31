from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.enums import CommandCategory, CommandStatus, OnDemandReadCommandOperation
from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.commands.on_demand_read_execution_orchestration import (
    orchestrate_on_demand_read_command_execution,
)
from app.modules.commands.on_demand_read_status_readback import (
    get_on_demand_read_execution_status,
)
from app.modules.commands.schemas import (
    ConsumeQueuedOnDemandReadExecutionRequest,
    ConsumeQueuedOnDemandReadExecutionResponse,
    ConsumeQueuedOnDemandReadExecutionResult,
    OnDemandReadExecutionOrchestrationRequest,
    OnDemandReadQueuedExecutionEnqueueRequest,
    OnDemandReadQueuedExecutionEnqueueResponse,
    OnDemandReadQueuedExecutionEnqueueResult,
    OnDemandReadQueuedExecutionLease,
    OnDemandReadQueuedExecutionMessage,
    OnDemandReadQueuedExecutionMessageSource,
)
from app.modules.commands.service import (
    _validate_on_demand_read_normalized_payload,
    apply_command_status_transition,
    get_meter_command,
    serialize_command_attempt,
    serialize_meter_command,
)
from app.modules.jobs.models import JobRun
from app.modules.jobs.service import serialize_job_run
from app.modules.readings.enums import SnapshotType
from app.runtime.redis_client import create_redis_client
from app.runtime.redis_transport import get_redis_transport_config
from app.runtime.schemas import RedisDispatchAckRequest, RedisDispatchDequeueClaimRequest
from app.runtime.services import (
    ack_redis_dispatch_message,
    dequeue_and_claim_redis_dispatch_message,
)
from app.runtime.services.runtime_artifact_utils import merge_runtime_metadata

ON_DEMAND_READ_QUEUE_CONTRACT_FAMILY = "on_demand_read_queued_execution"
ON_DEMAND_READ_QUEUE_CONTRACT_VERSION = "v1"
ON_DEMAND_READ_QUEUE_DISPATCH_CATEGORY = "on_demand_read_queued_execution"
ON_DEMAND_READ_QUEUE_INTENDED_WORKER_PATH = "commands.on_demand_read.queue_worker"
ON_DEMAND_READ_QUEUE_ROUTING_KEY = "commands.on_demand_read.queued_execution"
ON_DEMAND_READ_QUEUE_EXECUTOR_PREFIX = "on_demand_read_queue_worker"


def enqueue_on_demand_read_command_execution(
    session: Session,
    *,
    command_id: uuid.UUID,
    payload: OnDemandReadQueuedExecutionEnqueueRequest,
) -> OnDemandReadQueuedExecutionEnqueueResponse:
    command = get_meter_command(session, command_id)
    existing_artifact = _load_on_demand_read_queue_enqueue_artifact(command.result_summary)
    if existing_artifact is not None:
        return _build_existing_enqueue_response(
            command=command,
            payload=payload,
            artifact=existing_artifact,
        )

    _assert_on_demand_read_queue_enqueue_eligible(session, command=command)
    queue_message = _build_on_demand_read_queue_message(command=command, payload=payload)
    transport_config = get_redis_transport_config()
    dispatch_request_identity = _build_dispatch_request_identity(
        command_id=command.id,
        enqueue_identifier=payload.enqueue_identifier,
    )
    fields = _build_redis_stream_fields(
        command=command,
        queue_message=queue_message,
        dispatch_request_identity=dispatch_request_identity,
    )

    try:
        message_id = str(create_redis_client().xadd(transport_config.stream_name, fields=fields))
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis queue backend is unavailable for on-demand-read enqueue.",
        ) from exc

    enqueued_at = datetime.now(UTC)
    apply_command_status_transition(command, new_status=CommandStatus.QUEUED, now=enqueued_at)
    queue_artifact = _build_on_demand_read_queue_enqueue_artifact(
        command=command,
        queue_message=queue_message,
        enqueue_identifier=payload.enqueue_identifier,
        enqueue_reason=payload.enqueue_reason,
        dispatch_request_identity=dispatch_request_identity,
        stream_name=transport_config.stream_name,
        message_id=message_id,
        enqueued_at=enqueued_at,
        reused_existing_enqueue=False,
    )
    command.result_summary = merge_runtime_metadata(
        command.result_summary,
        {"on_demand_read_queue_enqueue": queue_artifact},
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return OnDemandReadQueuedExecutionEnqueueResponse(
        result=OnDemandReadQueuedExecutionEnqueueResult(
            queue_status=str(queue_artifact["queue_status"]),
            command_id=command.id,
            enqueue_identifier=str(queue_artifact["enqueue_identifier"]),
            dispatch_request_identity=str(queue_artifact["dispatch_request_identity"]),
            stream_name=str(queue_artifact["stream_name"]),
            message_id=str(queue_artifact["message_id"]),
            intended_worker_path=str(queue_artifact["intended_worker_path"]),
            on_demand_read_operation=queue_message.on_demand_read_operation,
            snapshot_type=queue_message.snapshot_type,
            reused_existing_enqueue=False,
            enqueued_at=enqueued_at,
            queue_artifact=queue_artifact,
            queue_message=queue_message,
        ),
        related_command=serialize_meter_command(command),
    )


def consume_next_queued_on_demand_read_execution(
    session: Session,
    *,
    payload: ConsumeQueuedOnDemandReadExecutionRequest,
) -> ConsumeQueuedOnDemandReadExecutionResponse:
    claimed_at = datetime.now(UTC)
    claim_result = dequeue_and_claim_redis_dispatch_message(
        RedisDispatchDequeueClaimRequest(
            worker_identifier=payload.worker_identifier,
            block_ms=payload.block_ms,
            ensure_consumer_group=payload.ensure_consumer_group,
        )
    )
    if claim_result.message is None or claim_result.claim is None or claim_result.dequeue is None:
        return ConsumeQueuedOnDemandReadExecutionResponse(
            result=ConsumeQueuedOnDemandReadExecutionResult(
                consume_status="empty",
                worker_identifier=payload.worker_identifier,
                queue_message_present=False,
                acked=False,
                consumed_at=claimed_at,
            )
        )

    queue_message = _validate_claimed_on_demand_read_queue_message(claim_result.message)
    command = get_meter_command(session, queue_message.source.command_id)
    enqueue_artifact = _load_on_demand_read_queue_enqueue_artifact(command.result_summary)
    if enqueue_artifact is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read command is missing the durable queue enqueue artifact.",
        )
    if enqueue_artifact.get("enqueue_identifier") != queue_message.enqueue_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed on-demand-read queue message does not match the durable enqueue artifact.",
        )

    orchestration = orchestrate_on_demand_read_command_execution(
        session,
        command_id=command.id,
        payload=OnDemandReadExecutionOrchestrationRequest(
            orchestration_identifier=_build_queue_orchestration_identifier(
                queue_message.enqueue_identifier
            ),
            executor_identifier=_build_queue_executor_identifier(payload.worker_identifier),
            orchestration_reason=payload.consume_reason or "on-demand-read-queued-execution",
            lease_seconds=payload.lease_seconds,
            session_timeout_seconds=payload.session_timeout_seconds,
        ),
    )
    attempt = session.get(CommandExecutionAttempt, orchestration.created_or_existing_attempt.id)
    refreshed_command = session.get(MeterCommand, command.id)
    job_run = (
        session.get(JobRun, attempt.job_run_id)
        if attempt is not None and attempt.job_run_id is not None
        else None
    )
    if attempt is None or refreshed_command is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read queued worker execution could not load durable execution state.",
        )

    status_response = get_on_demand_read_execution_status(session, command_id=refreshed_command.id)
    ack_result = ack_redis_dispatch_message(
        RedisDispatchAckRequest(
            worker_identifier=payload.worker_identifier,
            message_id=claim_result.message.message_id,
            claim_token=claim_result.claim.claim_token,
        )
    )
    consumed_at = datetime.now(UTC)
    queue_lease = _build_queue_lease(claim_result=claim_result)
    queue_consumption_record = _build_on_demand_read_queue_consumption_record(
        command=refreshed_command,
        attempt=attempt,
        job_run=job_run,
        queue_message=queue_message,
        queue_lease=queue_lease,
        worker_identifier=payload.worker_identifier,
        on_demand_read_execution_outcome=status_response.result.on_demand_read_execution_outcome,
        runtime_on_demand_read_execution_record_id=(
            status_response.result.runtime_on_demand_read_execution_record_id
        ),
        ack_receipt_id=ack_result.ack_receipt_id,
        acked_at=ack_result.acked_at,
        consumed_at=consumed_at,
    )
    artifact_payload = {"on_demand_read_queue_consumption": queue_consumption_record}
    attempt.execution_metadata = merge_runtime_metadata(attempt.execution_metadata, artifact_payload)
    refreshed_command.result_summary = merge_runtime_metadata(
        refreshed_command.result_summary,
        artifact_payload,
    )
    if job_run is not None:
        job_run.result_summary = merge_runtime_metadata(job_run.result_summary, artifact_payload)
        session.add(job_run)
    session.add_all([attempt, refreshed_command])
    session.commit()
    session.refresh(attempt)
    session.refresh(refreshed_command)
    if job_run is not None:
        session.refresh(job_run)
    return ConsumeQueuedOnDemandReadExecutionResponse(
        result=ConsumeQueuedOnDemandReadExecutionResult(
            consume_status="consumed",
            worker_identifier=payload.worker_identifier,
            queue_message_present=True,
            acked=True,
            consumed_at=consumed_at,
            command_id=refreshed_command.id,
            command_execution_attempt_id=attempt.id,
            job_run_id=job_run.id if job_run is not None else None,
            enqueue_identifier=queue_message.enqueue_identifier,
            on_demand_read_operation=queue_message.on_demand_read_operation,
            snapshot_type=queue_message.snapshot_type,
            on_demand_read_execution_outcome=(
                status_response.result.on_demand_read_execution_outcome
            ),
            runtime_on_demand_read_execution_record_id=(
                status_response.result.runtime_on_demand_read_execution_record_id
            ),
            queue_lease=queue_lease,
            queue_message=queue_message,
            queue_consumption_record=queue_consumption_record,
        ),
        related_command=serialize_meter_command(refreshed_command),
        created_or_existing_attempt=serialize_command_attempt(attempt),
        job_run=serialize_job_run(job_run).model_dump(mode="json") if job_run is not None else None,
    )


def _build_existing_enqueue_response(
    *,
    command: MeterCommand,
    payload: OnDemandReadQueuedExecutionEnqueueRequest,
    artifact: dict[str, object],
) -> OnDemandReadQueuedExecutionEnqueueResponse:
    if artifact.get("enqueue_identifier") != payload.enqueue_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read command already has a queued execution owned by another enqueue identifier.",
        )
    queue_message = OnDemandReadQueuedExecutionMessage.model_validate(artifact["queue_message"])
    enqueued_at = datetime.fromisoformat(str(artifact["enqueued_at"]))
    return OnDemandReadQueuedExecutionEnqueueResponse(
        result=OnDemandReadQueuedExecutionEnqueueResult(
            queue_status=str(artifact["queue_status"]),
            command_id=command.id,
            enqueue_identifier=str(artifact["enqueue_identifier"]),
            dispatch_request_identity=str(artifact["dispatch_request_identity"]),
            stream_name=str(artifact["stream_name"]),
            message_id=str(artifact["message_id"]),
            intended_worker_path=str(artifact["intended_worker_path"]),
            on_demand_read_operation=queue_message.on_demand_read_operation,
            snapshot_type=queue_message.snapshot_type,
            reused_existing_enqueue=True,
            enqueued_at=enqueued_at,
            queue_artifact=artifact,
            queue_message=queue_message,
        ),
        related_command=serialize_meter_command(command),
    )


def _assert_on_demand_read_queue_enqueue_eligible(
    session: Session,
    *,
    command: MeterCommand,
) -> None:
    if command.command_template.category != CommandCategory.ON_DEMAND_READ:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected command is not compatible with the on-demand-read queued execution slice.",
        )
    if command.current_status not in {
        CommandStatus.PENDING,
        CommandStatus.SCHEDULED,
        CommandStatus.RETRY_WAIT,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read command is not queue-eligible from its current state.",
        )
    latest_attempt = session.scalar(
        select(CommandExecutionAttempt)
        .where(CommandExecutionAttempt.meter_command_id == command.id)
        .order_by(CommandExecutionAttempt.attempt_number.desc())
    )
    if latest_attempt is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="On-demand-read command already has execution attempt history and cannot enter the bounded queued foundation.",
        )
    _validate_on_demand_read_normalized_payload(command)


def _build_on_demand_read_queue_message(
    *,
    command: MeterCommand,
    payload: OnDemandReadQueuedExecutionEnqueueRequest,
) -> OnDemandReadQueuedExecutionMessage:
    normalized_payload = _validate_on_demand_read_normalized_payload(command)
    return OnDemandReadQueuedExecutionMessage(
        contract_family=ON_DEMAND_READ_QUEUE_CONTRACT_FAMILY,
        contract_version=ON_DEMAND_READ_QUEUE_CONTRACT_VERSION,
        enqueue_identifier=payload.enqueue_identifier,
        command_category=CommandCategory.ON_DEMAND_READ,
        on_demand_read_operation=OnDemandReadCommandOperation(
            str(normalized_payload["on_demand_read_operation"])
        ),
        snapshot_type=SnapshotType(str(normalized_payload["on_demand_read"]["snapshot_type"])),
        intended_worker_path=ON_DEMAND_READ_QUEUE_INTENDED_WORKER_PATH,
        source=OnDemandReadQueuedExecutionMessageSource(
            command_id=command.id,
            meter_id=command.meter_id,
            endpoint_assignment_id=command.endpoint_assignment_id,
            protocol_association_profile_id=command.protocol_association_profile_id,
            correlation_id=command.correlation_id,
        ),
    )


def _build_dispatch_request_identity(
    *,
    command_id: uuid.UUID,
    enqueue_identifier: str,
) -> str:
    return f"on-demand-read-queue:{command_id}:{enqueue_identifier}"


def _build_redis_stream_fields(
    *,
    command: MeterCommand,
    queue_message: OnDemandReadQueuedExecutionMessage,
    dispatch_request_identity: str,
) -> dict[str, str]:
    return {
        "backend_name": "redis",
        "message_type": ON_DEMAND_READ_QUEUE_CONTRACT_FAMILY,
        "payload_version": ON_DEMAND_READ_QUEUE_CONTRACT_VERSION,
        "dispatch_category": ON_DEMAND_READ_QUEUE_DISPATCH_CATEGORY,
        "dispatch_request_identity": dispatch_request_identity,
        "routing_key": ON_DEMAND_READ_QUEUE_ROUTING_KEY,
        "source_identifiers": json.dumps(
            {
                "command_id": str(command.id),
                "meter_id": str(command.meter_id),
                "endpoint_assignment_id": (
                    str(command.endpoint_assignment_id)
                    if command.endpoint_assignment_id is not None
                    else None
                ),
                "protocol_association_profile_id": (
                    str(command.protocol_association_profile_id)
                    if command.protocol_association_profile_id is not None
                    else None
                ),
            },
            sort_keys=True,
        ),
        "correlation_lineage": json.dumps(
            {
                "command_correlation_id": command.correlation_id,
                "enqueue_identifier": queue_message.enqueue_identifier,
            },
            sort_keys=True,
        ),
        "dispatch_metadata": json.dumps(
            {
                "contract_family": ON_DEMAND_READ_QUEUE_CONTRACT_FAMILY,
                "contract_version": ON_DEMAND_READ_QUEUE_CONTRACT_VERSION,
                "command_category": CommandCategory.ON_DEMAND_READ.value,
                "on_demand_read_operation": queue_message.on_demand_read_operation.value,
                "snapshot_type": queue_message.snapshot_type.value,
            },
            sort_keys=True,
        ),
        "intended_worker_path": ON_DEMAND_READ_QUEUE_INTENDED_WORKER_PATH,
        "body": json.dumps(queue_message.model_dump(mode="json"), sort_keys=True),
    }


def _build_on_demand_read_queue_enqueue_artifact(
    *,
    command: MeterCommand,
    queue_message: OnDemandReadQueuedExecutionMessage,
    enqueue_identifier: str,
    enqueue_reason: str | None,
    dispatch_request_identity: str,
    stream_name: str,
    message_id: str,
    enqueued_at: datetime,
    reused_existing_enqueue: bool,
) -> dict[str, object]:
    return {
        "queue_status": "enqueued",
        "command_id": str(command.id),
        "enqueue_identifier": enqueue_identifier,
        "enqueue_reason": enqueue_reason,
        "dispatch_request_identity": dispatch_request_identity,
        "stream_name": stream_name,
        "message_id": message_id,
        "intended_worker_path": ON_DEMAND_READ_QUEUE_INTENDED_WORKER_PATH,
        "contract_family": ON_DEMAND_READ_QUEUE_CONTRACT_FAMILY,
        "contract_version": ON_DEMAND_READ_QUEUE_CONTRACT_VERSION,
        "on_demand_read_operation": queue_message.on_demand_read_operation.value,
        "snapshot_type": queue_message.snapshot_type.value,
        "reused_existing_enqueue": reused_existing_enqueue,
        "enqueued_at": enqueued_at.isoformat(),
        "queue_message": queue_message.model_dump(mode="json"),
    }


def _validate_claimed_on_demand_read_queue_message(claimed_message) -> OnDemandReadQueuedExecutionMessage:
    if claimed_message.dispatch_category != ON_DEMAND_READ_QUEUE_DISPATCH_CATEGORY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message is not compatible with the on-demand-read queued execution slice.",
        )
    if claimed_message.intended_worker_path != ON_DEMAND_READ_QUEUE_INTENDED_WORKER_PATH:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message is not routed to the on-demand-read queue worker path.",
        )
    queue_message = OnDemandReadQueuedExecutionMessage.model_validate(claimed_message.body)
    if queue_message.contract_family != ON_DEMAND_READ_QUEUE_CONTRACT_FAMILY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed dispatch message is not owned by the on-demand-read queued execution contract.",
        )
    if queue_message.contract_version != ON_DEMAND_READ_QUEUE_CONTRACT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed on-demand-read queue message uses an unsupported contract version.",
        )
    if queue_message.command_category != CommandCategory.ON_DEMAND_READ:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed queue message is not for an on-demand-read command.",
        )
    if queue_message.on_demand_read_operation != OnDemandReadCommandOperation.READ_BILLING_SNAPSHOT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed queue message is not for the bounded billing snapshot on-demand-read operation.",
        )
    if queue_message.snapshot_type != SnapshotType.BILLING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed queue message is not for the bounded billing snapshot contract.",
        )
    return queue_message


def _build_queue_orchestration_identifier(enqueue_identifier: str) -> str:
    return f"on-demand-read-queue-orchestrator:{enqueue_identifier}"


def _build_queue_executor_identifier(worker_identifier: str) -> str:
    return f"{ON_DEMAND_READ_QUEUE_EXECUTOR_PREFIX}:{worker_identifier}"


def _build_queue_lease(*, claim_result) -> OnDemandReadQueuedExecutionLease:
    if claim_result.claim is None or claim_result.dequeue is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claimed queue message does not include a valid lease contract.",
        )
    return OnDemandReadQueuedExecutionLease(
        stream_name=claim_result.stream_name,
        consumer_group=claim_result.consumer_group,
        consumer_name=claim_result.consumer_name,
        message_id=claim_result.claim.pending_message_id,
        claim_token=claim_result.claim.claim_token,
        claim_timeout_seconds=claim_result.claim.claim_timeout_seconds,
        delivery_count=claim_result.dequeue.delivery_count,
    )


def _build_on_demand_read_queue_consumption_record(
    *,
    command: MeterCommand,
    attempt: CommandExecutionAttempt,
    job_run: JobRun | None,
    queue_message: OnDemandReadQueuedExecutionMessage,
    queue_lease: OnDemandReadQueuedExecutionLease,
    worker_identifier: str,
    on_demand_read_execution_outcome: str | None,
    runtime_on_demand_read_execution_record_id: str | None,
    ack_receipt_id: str,
    acked_at: str,
    consumed_at: datetime,
) -> dict[str, object]:
    execution_metadata = attempt.execution_metadata or {}
    return {
        "consume_status": "consumed",
        "worker_identifier": worker_identifier,
        "command_id": str(command.id),
        "command_execution_attempt_id": str(attempt.id),
        "job_run_id": str(job_run.id) if job_run is not None else None,
        "enqueue_identifier": queue_message.enqueue_identifier,
        "queue_message_id": queue_lease.message_id,
        "claim_token": queue_lease.claim_token,
        "ack_receipt_id": ack_receipt_id,
        "acked_at": acked_at,
        "runtime_on_demand_read_execution_record_id": runtime_on_demand_read_execution_record_id,
        "on_demand_read_operation": queue_message.on_demand_read_operation.value,
        "snapshot_type": queue_message.snapshot_type.value,
        "on_demand_read_execution_outcome": on_demand_read_execution_outcome,
        "orchestration_artifact_present": "on_demand_read_execution_orchestration"
        in execution_metadata,
        "terminalization_artifact_present": "on_demand_read_runtime_terminalization"
        in execution_metadata,
        "queue_lease": queue_lease.model_dump(mode="json"),
        "queue_message": queue_message.model_dump(mode="json"),
        "consumed_at": consumed_at.isoformat(),
    }


def _load_on_demand_read_queue_enqueue_artifact(
    result_summary: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(result_summary, dict):
        return None
    payload = result_summary.get("on_demand_read_queue_enqueue")
    return payload if isinstance(payload, dict) else None
