from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.jobs.models import JobRun
from app.modules.jobs.service import CLAIMABLE_JOB_STATUSES, get_job_run, serialize_job_run
from app.runtime.contracts import (
    DerivedWorkPickupCategory,
    DerivedWorkRoutingCategory,
    DerivedWorkRoutingResult,
)
from app.runtime.schemas import DerivedWorkPickupProjection, DerivedWorkPickupResponse


def list_derived_work_for_pickup(
    session: Session,
    *,
    pickup_category: DerivedWorkPickupCategory | None = None,
    limit: int = 100,
) -> DerivedWorkPickupResponse:
    now = datetime.now(UTC)
    statement = (
        select(JobRun)
        .where(
            JobRun.status.in_(list(CLAIMABLE_JOB_STATUSES)),
            JobRun.available_at <= now,
            JobRun.result_summary["derived_work_routing"]["is_derived_work"].astext == "true",
        )
        .order_by(JobRun.available_at.asc(), JobRun.scheduled_for.asc())
        .limit(limit)
    )
    job_runs = session.scalars(statement).all()

    retry_items: list[DerivedWorkPickupProjection] = []
    followup_items: list[DerivedWorkPickupProjection] = []

    for job_run in job_runs:
        projection = build_derived_work_pickup_projection(job_run)
        if projection is None:
            continue
        if pickup_category is not None and projection.pickup_category != pickup_category:
            continue
        if projection.pickup_category == DerivedWorkPickupCategory.RETRY_PICKUP:
            retry_items.append(projection)
        else:
            followup_items.append(projection)

    return DerivedWorkPickupResponse(
        total=len(retry_items) + len(followup_items),
        retry_items=retry_items,
        followup_items=followup_items,
    )


def get_eligible_derived_work_pickup_projection(
    session: Session,
    *,
    job_run_id,
) -> DerivedWorkPickupProjection:
    job_run = get_job_run(session, job_run_id)
    now = datetime.now(UTC)
    if job_run.status not in CLAIMABLE_JOB_STATUSES or job_run.available_at > now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job run is not currently eligible for derived-work pickup.",
        )
    projection = build_derived_work_pickup_projection(job_run)
    if projection is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job run does not have an eligible derived-work pickup projection.",
        )
    return projection


def build_derived_work_pickup_projection(job_run: JobRun) -> DerivedWorkPickupProjection | None:
    result_summary = job_run.result_summary or {}
    if not isinstance(result_summary, dict):
        return None
    derived_payload = result_summary.get("derived_work_routing")
    if not isinstance(derived_payload, dict):
        return None

    routing = DerivedWorkRoutingResult.model_validate(derived_payload)
    if not routing.is_derived_work or routing.routing_category is None:
        return None

    pickup_category = _map_routing_to_pickup_category(routing.routing_category)
    return DerivedWorkPickupProjection(
        job_run=serialize_job_run(job_run),
        pickup_category=pickup_category,
        routing_category=routing.routing_category,
        lineage=routing.lineage,
        eligible_for_retry_pickup=pickup_category == DerivedWorkPickupCategory.RETRY_PICKUP,
        eligible_for_followup_pickup=pickup_category == DerivedWorkPickupCategory.FOLLOWUP_PICKUP,
    )


def _map_routing_to_pickup_category(
    routing_category: DerivedWorkRoutingCategory,
) -> DerivedWorkPickupCategory:
    if routing_category == DerivedWorkRoutingCategory.RETRY_PATH:
        return DerivedWorkPickupCategory.RETRY_PICKUP
    return DerivedWorkPickupCategory.FOLLOWUP_PICKUP
