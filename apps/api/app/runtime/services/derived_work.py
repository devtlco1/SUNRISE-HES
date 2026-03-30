from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.jobs.models import JobRun
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.contracts import (
    DerivedWorkLineage,
    DerivedWorkRoutingCategory,
    DerivedWorkRoutingResult,
    DownstreamFollowUpActionType,
)
from app.runtime.schemas import ConsumeDerivedWorkResponse


def consume_derived_work_job_run(
    session: Session,
    *,
    job_run_id: uuid.UUID,
) -> ConsumeDerivedWorkResponse:
    job_run = get_job_run(session, job_run_id)
    routing = inspect_and_route_derived_work(job_run)
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"derived_work_routing": routing.model_dump()},
    )
    session.add(job_run)
    session.commit()
    session.refresh(job_run)
    return ConsumeDerivedWorkResponse(job_run=serialize_job_run(job_run), routing=routing)


def inspect_and_route_derived_work(job_run: JobRun) -> DerivedWorkRoutingResult:
    request_payload = job_run.request_payload or {}
    if not isinstance(request_payload, dict):
        return DerivedWorkRoutingResult(
            is_derived_work=False,
            summary={"reason": "Job run has no derived-work request payload."},
        )

    follow_up = request_payload.get("follow_up")
    lineage = request_payload.get("lineage")
    if not isinstance(follow_up, dict) or not isinstance(lineage, dict):
        return DerivedWorkRoutingResult(
            is_derived_work=False,
            summary={"reason": "Job run is not tagged as follow-up derived work."},
        )

    action_type_raw = follow_up.get("action_type")
    if not isinstance(action_type_raw, str):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Derived work payload is missing a valid follow-up action type.",
        )

    action_type = DownstreamFollowUpActionType(action_type_raw)
    routing_category = _map_action_type_to_routing_category(action_type)
    derived_lineage = DerivedWorkLineage(
        source_attempt_id=lineage.get("source_attempt_id"),
        source_command_id=lineage.get("source_command_id"),
        source_job_run_id=lineage.get("source_job_run_id"),
        source_correlation_id=lineage.get("source_correlation_id"),
    )
    return DerivedWorkRoutingResult(
        is_derived_work=True,
        action_type=action_type,
        routing_category=routing_category,
        lineage=derived_lineage,
        summary={
            "routing_category": routing_category.value,
            "action_type": action_type.value,
            "source_attempt_id": derived_lineage.source_attempt_id,
            "source_command_id": derived_lineage.source_command_id,
            "source_job_run_id": derived_lineage.source_job_run_id,
            "source_correlation_id": derived_lineage.source_correlation_id,
            "derived_correlation_id": job_run.correlation_id,
        },
    )


def _map_action_type_to_routing_category(
    action_type: DownstreamFollowUpActionType,
) -> DerivedWorkRoutingCategory:
    if action_type == DownstreamFollowUpActionType.RETRY:
        return DerivedWorkRoutingCategory.RETRY_PATH
    return DerivedWorkRoutingCategory.FOLLOWUP_PATH


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
