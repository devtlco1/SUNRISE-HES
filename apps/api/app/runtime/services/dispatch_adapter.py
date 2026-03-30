from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.jobs.models import JobRun
from app.modules.jobs.service import CLAIMABLE_JOB_STATUSES, get_job_run, serialize_job_run
from app.runtime.contracts import (
    DerivedWorkCoordinationCategory,
    DerivedWorkDispatchCategory,
)
from app.runtime.schemas import (
    DerivedWorkCoordinationProjection,
    DerivedWorkDispatchRequestProjection,
    DerivedWorkDispatchRequestResponse,
)
from app.runtime.services.coordinator import build_dispatch_ready_projection


def list_derived_work_dispatch_requests(
    session: Session,
    *,
    dispatch_category: DerivedWorkDispatchCategory | None = None,
    limit: int = 100,
) -> DerivedWorkDispatchRequestResponse:
    now = datetime.now(UTC)
    statement = (
        select(JobRun)
        .where(
            JobRun.status.in_(list(CLAIMABLE_JOB_STATUSES)),
            JobRun.available_at <= now,
            JobRun.result_summary["derived_work_handler"]["handled"].astext == "true",
        )
        .order_by(JobRun.available_at.asc(), JobRun.scheduled_for.asc())
        .limit(limit)
    )
    job_runs = session.scalars(statement).all()

    retry_items: list[DerivedWorkDispatchRequestProjection] = []
    followup_items: list[DerivedWorkDispatchRequestProjection] = []

    for job_run in job_runs:
        coordination = build_dispatch_ready_projection(job_run)
        if coordination is None:
            continue
        dispatch_request = build_dispatch_request_projection(coordination)
        if dispatch_category is not None and dispatch_request.dispatch_category != dispatch_category:
            continue
        if dispatch_request.dispatch_category == DerivedWorkDispatchCategory.RETRY_DISPATCH_REQUEST:
            retry_items.append(dispatch_request)
        else:
            followup_items.append(dispatch_request)

    return DerivedWorkDispatchRequestResponse(
        total=len(retry_items) + len(followup_items),
        retry_items=retry_items,
        followup_items=followup_items,
    )


def get_dispatch_request_projection(
    session: Session,
    *,
    job_run_id,
) -> DerivedWorkDispatchRequestProjection:
    job_run = get_job_run(session, job_run_id)
    now = datetime.now(UTC)
    if job_run.status not in CLAIMABLE_JOB_STATUSES or job_run.available_at > now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job run is not currently eligible for dispatch request adaptation.",
        )
    coordination = build_dispatch_ready_projection(job_run)
    if coordination is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job run does not have a dispatch-ready coordination projection.",
        )
    return build_dispatch_request_projection(coordination)


def build_dispatch_request_projection(
    coordination: DerivedWorkCoordinationProjection,
) -> DerivedWorkDispatchRequestProjection:
    dispatch_category = _map_coordination_to_dispatch_category(coordination.coordination_category)
    return DerivedWorkDispatchRequestProjection(
        job_run=coordination.job_run,
        dispatch_category=dispatch_category,
        source_job_run_id=str(coordination.job_run.id),
        lineage=coordination.lineage,
        derived_correlation_id=coordination.job_run.correlation_id,
        dispatch_ready_metadata={
            "coordination_category": coordination.coordination_category.value,
            "handler_category": coordination.handler_category.value,
            "dispatch_ready": coordination.dispatch_ready,
        },
        intended_path=_map_dispatch_category_to_intended_path(dispatch_category),
    )


def _map_coordination_to_dispatch_category(
    coordination_category: DerivedWorkCoordinationCategory,
) -> DerivedWorkDispatchCategory:
    if coordination_category == DerivedWorkCoordinationCategory.RETRY_DISPATCH_READY:
        return DerivedWorkDispatchCategory.RETRY_DISPATCH_REQUEST
    return DerivedWorkDispatchCategory.FOLLOWUP_DISPATCH_REQUEST


def _map_dispatch_category_to_intended_path(
    dispatch_category: DerivedWorkDispatchCategory,
) -> str:
    if dispatch_category == DerivedWorkDispatchCategory.RETRY_DISPATCH_REQUEST:
        return "retry_handler_worker_path"
    return "followup_handler_worker_path"
