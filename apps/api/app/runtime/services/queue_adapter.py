from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.jobs.service import get_job_run, serialize_job_run
from app.runtime.queue_adapters import queue_adapter_registry
from app.runtime.schemas import QueueAdaptersResponse, QueueAdapterDescriptorResponse, QueueEnqueueResponse
from app.runtime.services.dispatch_adapter import get_dispatch_request_projection
from app.runtime.services.queue_payload import build_queue_enqueue_payload


def enqueue_dispatch_request_for_job_run(
    session: Session,
    *,
    job_run_id: uuid.UUID,
) -> QueueEnqueueResponse:
    job_run = get_job_run(session, job_run_id)
    existing = _load_existing_enqueue_result(job_run.result_summary)
    if existing is not None:
        return QueueEnqueueResponse(job_run=serialize_job_run(job_run), enqueue_result=existing)

    dispatch_request = get_dispatch_request_projection(session, job_run_id=job_run_id)
    enqueue_payload = build_queue_enqueue_payload(dispatch_request)
    adapter = queue_adapter_registry.resolve_configured()
    enqueue_result = adapter.enqueue(enqueue_payload)
    job_run.result_summary = _merge_dicts(
        job_run.result_summary,
        {"queue_enqueue": enqueue_result.model_dump()},
    )
    session.add(job_run)
    session.commit()
    session.refresh(job_run)
    return QueueEnqueueResponse(job_run=serialize_job_run(job_run), enqueue_result=enqueue_result)


def list_queue_adapters() -> QueueAdaptersResponse:
    return QueueAdaptersResponse(
        active_backend=settings.queue_backend,
        items=[
            QueueAdapterDescriptorResponse(
                code=item.code,
                implementation=item.implementation,
                is_default=item.is_default,
                capabilities=item.capabilities,
            )
            for item in queue_adapter_registry.list_descriptors()
        ],
    )


def _load_existing_enqueue_result(result_summary: dict[str, object] | None):
    from app.runtime.contracts import QueueEnqueueResult

    if not isinstance(result_summary, dict):
        return None
    payload = result_summary.get("queue_enqueue")
    if not isinstance(payload, dict):
        return None
    return QueueEnqueueResult.model_validate(payload)


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
