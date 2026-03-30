from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.jobs.models import JobRun
from app.modules.jobs.service import CLAIMABLE_JOB_STATUSES, serialize_job_run
from app.runtime.contracts import (
    DerivedWorkCoordinationCategory,
    DerivedWorkHandlerCategory,
    DerivedWorkHandlerResult,
)
from app.runtime.schemas import DerivedWorkCoordinationProjection, DerivedWorkCoordinationResponse


def list_dispatch_ready_derived_work(
    session: Session,
    *,
    coordination_category: DerivedWorkCoordinationCategory | None = None,
    limit: int = 100,
) -> DerivedWorkCoordinationResponse:
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

    retry_items: list[DerivedWorkCoordinationProjection] = []
    followup_items: list[DerivedWorkCoordinationProjection] = []

    for job_run in job_runs:
        projection = build_dispatch_ready_projection(job_run)
        if projection is None:
            continue
        if coordination_category is not None and projection.coordination_category != coordination_category:
            continue
        if projection.coordination_category == DerivedWorkCoordinationCategory.RETRY_DISPATCH_READY:
            retry_items.append(projection)
        else:
            followup_items.append(projection)

    return DerivedWorkCoordinationResponse(
        total=len(retry_items) + len(followup_items),
        retry_items=retry_items,
        followup_items=followup_items,
    )


def build_dispatch_ready_projection(job_run: JobRun) -> DerivedWorkCoordinationProjection | None:
    result_summary = job_run.result_summary or {}
    if not isinstance(result_summary, dict):
        return None
    handler_payload = result_summary.get("derived_work_handler")
    if not isinstance(handler_payload, dict):
        return None

    handler = DerivedWorkHandlerResult.model_validate(handler_payload)
    if not handler.handled or handler.handler_category is None:
        return None

    coordination_category = _map_handler_to_coordination_category(handler.handler_category)
    return DerivedWorkCoordinationProjection(
        job_run=serialize_job_run(job_run),
        coordination_category=coordination_category,
        handler_category=handler.handler_category,
        lineage=handler.lineage,
        dispatch_ready=True,
    )


def _map_handler_to_coordination_category(
    handler_category: DerivedWorkHandlerCategory,
) -> DerivedWorkCoordinationCategory:
    if handler_category == DerivedWorkHandlerCategory.RETRY_HANDLER:
        return DerivedWorkCoordinationCategory.RETRY_DISPATCH_READY
    return DerivedWorkCoordinationCategory.FOLLOWUP_DISPATCH_READY
