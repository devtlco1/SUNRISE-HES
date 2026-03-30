from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.jobs.enums import JobRunStatus
from app.modules.jobs.models import JobRun
from app.modules.jobs.service import serialize_job_run
from app.runtime.contracts import DownstreamFollowUpActionDescriptor, DownstreamFollowUpActionType
from app.runtime.schemas import FollowUpMaterializedRunResponse, MaterializeFollowUpActionsResponse


def materialize_follow_up_actions_for_attempt(
    session: Session,
    *,
    attempt_id: uuid.UUID,
) -> MaterializeFollowUpActionsResponse:
    attempt = session.get(CommandExecutionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command execution attempt not found.")
    if attempt.job_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Follow-up materialization requires an attempt linked to a job run.",
        )

    command = session.get(MeterCommand, attempt.meter_command_id)
    job_run = session.get(JobRun, attempt.job_run_id)
    if command is None or job_run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Follow-up materialization requires source command and job run context.",
        )

    actions = _load_follow_up_actions(attempt=attempt, command=command, job_run=job_run)
    if not actions:
        _persist_materialization_summary(
            attempt=attempt,
            command=command,
            job_run=job_run,
            summary={"materialized_count": 0, "existing_count": 0, "items": []},
        )
        session.add_all([attempt, command, job_run])
        session.commit()
        return MaterializeFollowUpActionsResponse(
            source_attempt_id=str(attempt.id),
            materialized_count=0,
            existing_count=0,
            items=[],
        )

    items: list[FollowUpMaterializedRunResponse] = []
    materialized_count = 0
    existing_count = 0
    base_now = datetime.now(UTC)

    for index, action in enumerate(actions):
        correlation_id = _build_follow_up_correlation_id(attempt_id=attempt.id, action=action)
        existing = session.scalar(select(JobRun).where(JobRun.correlation_id == correlation_id))
        if existing is not None:
            items.append(
                FollowUpMaterializedRunResponse(
                    action_type=action.action_type,
                    materialized=False,
                    job_run=serialize_job_run(existing),
                )
            )
            existing_count += 1
            continue

        scheduled_for = _compute_follow_up_schedule(base_now=base_now, action=action, index=index)
        follow_up_run = JobRun(
            job_definition_id=job_run.job_definition_id,
            target_meter_id=job_run.target_meter_id,
            target_endpoint_id=job_run.target_endpoint_id,
            related_command_id=command.id,
            scheduled_for=scheduled_for,
            available_at=scheduled_for,
            status=JobRunStatus.PENDING,
            correlation_id=correlation_id,
            max_retries=job_run.max_retries,
            retry_count=0,
            request_payload=_build_follow_up_request_payload(
                source_attempt_id=attempt.id,
                source_command_id=command.id,
                source_job_run_id=job_run.id,
                source_correlation_id=job_run.correlation_id or command.correlation_id,
                action=action,
            ),
        )
        session.add(follow_up_run)
        session.flush()
        items.append(
            FollowUpMaterializedRunResponse(
                action_type=action.action_type,
                materialized=True,
                job_run=serialize_job_run(follow_up_run),
            )
        )
        materialized_count += 1

    _persist_materialization_summary(
        attempt=attempt,
        command=command,
        job_run=job_run,
        summary={
            "materialized_count": materialized_count,
            "existing_count": existing_count,
            "items": [item.model_dump(mode="json") for item in items],
        },
    )
    session.add_all([attempt, command, job_run])
    session.commit()

    refreshed_items: list[FollowUpMaterializedRunResponse] = []
    for item in items:
        refreshed_run = session.get(JobRun, item.job_run.id)
        if refreshed_run is None:
            continue
        refreshed_items.append(
            FollowUpMaterializedRunResponse(
                action_type=item.action_type,
                materialized=item.materialized,
                job_run=serialize_job_run(refreshed_run),
            )
        )

    return MaterializeFollowUpActionsResponse(
        source_attempt_id=str(attempt.id),
        materialized_count=materialized_count,
        existing_count=existing_count,
        items=refreshed_items,
    )


def _load_follow_up_actions(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun,
) -> list[DownstreamFollowUpActionDescriptor]:
    for container in (
        attempt.execution_metadata,
        command.result_summary,
        job_run.result_summary,
    ):
        actions = _extract_actions_from_container(container)
        if actions:
            return actions
    return []


def _extract_actions_from_container(
    container: dict[str, object] | None,
) -> list[DownstreamFollowUpActionDescriptor]:
    if not isinstance(container, dict):
        return []

    for key in ("downstream_signal_consumption", "post_processing"):
        payload = container.get(key)
        if not isinstance(payload, dict):
            continue
        action_items = payload.get("follow_up_actions")
        if not isinstance(action_items, list):
            continue
        return [DownstreamFollowUpActionDescriptor.model_validate(item) for item in action_items]
    return []


def _build_follow_up_correlation_id(
    *,
    attempt_id: uuid.UUID,
    action: DownstreamFollowUpActionDescriptor,
) -> str:
    return f"followup:{attempt_id}:{action.action_type.value}"


def _compute_follow_up_schedule(
    *,
    base_now: datetime,
    action: DownstreamFollowUpActionDescriptor,
    index: int,
) -> datetime:
    delay_seconds = 0
    if isinstance(action.payload, dict):
        raw_delay = action.payload.get("retry_delay_seconds")
        if isinstance(raw_delay, int):
            delay_seconds = raw_delay
    return base_now + timedelta(seconds=delay_seconds + index)


def _build_follow_up_request_payload(
    *,
    source_attempt_id: uuid.UUID,
    source_command_id: uuid.UUID,
    source_job_run_id: uuid.UUID,
    source_correlation_id: str | None,
    action: DownstreamFollowUpActionDescriptor,
) -> dict[str, object]:
    return {
        "follow_up": {
            "action_type": action.action_type.value,
            "reason": action.reason,
            "payload": action.payload,
        },
        "lineage": {
            "source_attempt_id": str(source_attempt_id),
            "source_command_id": str(source_command_id),
            "source_job_run_id": str(source_job_run_id),
            "source_correlation_id": source_correlation_id,
        },
    }


def _persist_materialization_summary(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun,
    summary: dict[str, object],
) -> None:
    materialization_payload = {"follow_up_materialization": summary}
    attempt.execution_metadata = _merge_dicts(attempt.execution_metadata, materialization_payload)
    command.result_summary = _merge_dicts(command.result_summary, materialization_payload)
    job_run.result_summary = _merge_dicts(job_run.result_summary, materialization_payload)


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
