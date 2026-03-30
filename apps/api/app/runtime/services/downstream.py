from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.modules.connectivity.enums import ConnectivitySessionStatus
from app.modules.connectivity.models import ConnectivitySessionHistory
from app.modules.events.enums import EventSeverity, EventState
from app.modules.events.models import MeterEventIngestion
from app.modules.jobs.models import JobRun
from app.runtime.contracts import (
    DownstreamFollowUpActionDescriptor,
    DownstreamFollowUpActionType,
    DownstreamSignalConsumptionResult,
    EndpointHealthHint,
    EndpointHealthProjectionStatus,
    OperationalEventArtifact,
    RuntimePostProcessingResult,
)


def consume_downstream_signals(
    session: Session,
    *,
    post_processing: RuntimePostProcessingResult,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    session_history: ConnectivitySessionHistory,
    job_run: JobRun | None = None,
) -> DownstreamSignalConsumptionResult:
    follow_up_actions = _build_follow_up_actions(post_processing)
    endpoint_health_hint = _build_endpoint_health_hint(post_processing, session_history)
    operational_event = _build_operational_event(post_processing, attempt, command, session_history)
    event_created = False
    event_id = None

    if operational_event is not None and command.meter_id is not None:
        existing = session.scalar(
            select(MeterEventIngestion).where(
                MeterEventIngestion.related_attempt_id == attempt.id,
                MeterEventIngestion.event_code == operational_event.event_code,
            )
        )
        if existing is None:
            record = MeterEventIngestion(
                meter_id=command.meter_id,
                related_attempt_id=attempt.id,
                event_code=operational_event.event_code,
                event_name=operational_event.event_name,
                severity=operational_event.severity,
                event_state=operational_event.event_state,
                occurred_at=datetime.now(UTC),
                received_at=datetime.now(UTC),
                normalized_payload=operational_event.normalized_payload,
                correlation_id=command.correlation_id,
            )
            session.add(record)
            session.flush()
            event_created = True
            event_id = str(record.id)
        else:
            event_id = str(existing.id)

    summary = {
        "follow_up_action_count": len(follow_up_actions),
        "operational_event_created": event_created,
        "operational_event_id": event_id,
        "endpoint_health_hint": endpoint_health_hint.model_dump() if endpoint_health_hint is not None else None,
    }
    _persist_consumption_summary(
        attempt=attempt,
        command=command,
        job_run=job_run,
        session_history=session_history,
        summary=summary,
        follow_up_actions=follow_up_actions,
        endpoint_health_hint=endpoint_health_hint,
    )
    return DownstreamSignalConsumptionResult(
        follow_up_actions=follow_up_actions,
        operational_event_created=event_created,
        operational_event_id=event_id,
        endpoint_health_hint=endpoint_health_hint,
        summary=summary,
    )


def _build_follow_up_actions(
    post_processing: RuntimePostProcessingResult,
) -> list[DownstreamFollowUpActionDescriptor]:
    actions: list[DownstreamFollowUpActionDescriptor] = []
    if post_processing.signals.should_retry:
        actions.append(
            DownstreamFollowUpActionDescriptor(
                action_type=DownstreamFollowUpActionType.RETRY,
                reason=post_processing.retry.reason,
                payload={"retry_delay_seconds": post_processing.retry.retry_delay_seconds},
            )
        )
    if post_processing.signals.should_schedule_followup:
        actions.append(
            DownstreamFollowUpActionDescriptor(
                action_type=DownstreamFollowUpActionType.FOLLOWUP_SCHEDULE,
                reason="Partial success requires follow-up collection or review.",
                payload={"outcome_category": post_processing.outcome_category.value},
            )
        )
    return actions


def _build_endpoint_health_hint(
    post_processing: RuntimePostProcessingResult,
    session_history: ConnectivitySessionHistory,
) -> EndpointHealthHint | None:
    if not post_processing.signals.should_mark_endpoint_unhealthy:
        return None
    status = (
        EndpointHealthProjectionStatus.UNHEALTHY
        if session_history.status == ConnectivitySessionStatus.TIMED_OUT
        else EndpointHealthProjectionStatus.DEGRADED
    )
    return EndpointHealthHint(
        status=status,
        reason=post_processing.retry.reason,
        should_mark_endpoint_unhealthy=True,
        session_status=session_history.status,
    )


def _build_operational_event(
    post_processing: RuntimePostProcessingResult,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    session_history: ConnectivitySessionHistory,
) -> OperationalEventArtifact | None:
    if not post_processing.signals.should_raise_operational_event:
        return None
    severity = (
        EventSeverity.CRITICAL
        if post_processing.outcome_category.value in {"permanent_failure", "timeout"}
        else EventSeverity.WARNING
    )
    return OperationalEventArtifact(
        event_code=f"runtime_signal.{post_processing.outcome_category.value}",
        event_name="Runtime Outcome Signal",
        severity=severity,
        event_state=EventState.OPEN,
        normalized_payload={
            "attempt_id": str(attempt.id),
            "command_id": str(command.id),
            "session_history_id": str(session_history.id),
            "outcome_category": post_processing.outcome_category.value,
            "retry": post_processing.retry.model_dump(),
            "signals": post_processing.signals.model_dump(),
        },
    )


def _persist_consumption_summary(
    *,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
    job_run: JobRun | None,
    session_history: ConnectivitySessionHistory,
    summary: dict[str, object],
    follow_up_actions: list[DownstreamFollowUpActionDescriptor],
    endpoint_health_hint: EndpointHealthHint | None,
) -> None:
    downstream_payload = {
        "summary": summary,
        "follow_up_actions": [action.model_dump() for action in follow_up_actions],
        "endpoint_health_hint": endpoint_health_hint.model_dump() if endpoint_health_hint is not None else None,
    }
    attempt.execution_metadata = _merge_dicts(
        attempt.execution_metadata,
        {"downstream_signal_consumption": downstream_payload},
    )
    command.result_summary = _merge_dicts(
        command.result_summary,
        {"downstream_signal_consumption": downstream_payload},
    )
    if job_run is not None:
        job_run.result_summary = _merge_dicts(
            job_run.result_summary,
            {"downstream_signal_consumption": downstream_payload},
        )
    session_history.metadata_json = _merge_dicts(
        session_history.metadata_json,
        {"endpoint_health_hint": endpoint_health_hint.model_dump() if endpoint_health_hint is not None else None},
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
