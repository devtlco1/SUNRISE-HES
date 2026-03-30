from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.contracts import (
    DerivedWorkHandlerCategory,
    DerivedWorkHandlerResult,
    DerivedWorkPickupCategory,
)
from app.runtime.schemas import HandleDerivedWorkResponse
from app.runtime.services.pickup_policy import get_eligible_derived_work_pickup_projection


def handle_derived_work_job_run(
    session: Session,
    *,
    job_run_id: uuid.UUID,
) -> HandleDerivedWorkResponse:
    projection = get_eligible_derived_work_pickup_projection(session, job_run_id=job_run_id)
    job_run = get_job_run(session, job_run_id)
    handler_result = _build_handler_result(projection)
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"derived_work_handler": handler_result.model_dump()},
    )
    session.add(job_run)
    session.commit()
    session.refresh(job_run)
    return HandleDerivedWorkResponse(job_run=serialize_job_run(job_run), handler=handler_result)


def _build_handler_result(projection) -> DerivedWorkHandlerResult:
    handler_category = _map_pickup_to_handler_category(projection.pickup_category)
    return DerivedWorkHandlerResult(
        handled=True,
        handler_category=handler_category,
        pickup_category=projection.pickup_category,
        lineage=projection.lineage,
        should_remain_pending=True,
        summary={
            "handler_category": handler_category.value,
            "pickup_category": projection.pickup_category.value,
            "routing_category": projection.routing_category.value,
            "source_attempt_id": projection.lineage.source_attempt_id if projection.lineage else None,
            "source_command_id": projection.lineage.source_command_id if projection.lineage else None,
            "source_job_run_id": projection.lineage.source_job_run_id if projection.lineage else None,
            "source_correlation_id": projection.lineage.source_correlation_id if projection.lineage else None,
            "derived_correlation_id": projection.job_run.correlation_id,
            "should_remain_pending": True,
        },
    )


def _map_pickup_to_handler_category(
    pickup_category: DerivedWorkPickupCategory,
) -> DerivedWorkHandlerCategory:
    if pickup_category == DerivedWorkPickupCategory.RETRY_PICKUP:
        return DerivedWorkHandlerCategory.RETRY_HANDLER
    return DerivedWorkHandlerCategory.FOLLOWUP_HANDLER


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
