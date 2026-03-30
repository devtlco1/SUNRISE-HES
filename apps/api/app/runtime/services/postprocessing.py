from __future__ import annotations

from app.modules.commands.models import CommandExecutionAttempt, MeterCommand
from app.runtime.contracts import (
    RuntimeCommandOutcome,
    RuntimeCommandResult,
    RuntimeOutcomeCategory,
    RuntimePostProcessingResult,
    RuntimeRetryPolicyDecision,
    RuntimeDownstreamSignals,
    RuntimeSessionResult,
)
from app.runtime.services.ingestion import RuntimeIngestionPersistenceResult

TRANSPORT_RETRYABLE_ERROR_CODES = {
    "connection_refused",
    "network_unreachable",
    "no_route",
    "runtime_adapter_execution_error",
    "session_unavailable",
    "temporary_transport_failure",
    "transport_unavailable",
}

PERMANENT_AUTH_ERROR_CODES = {
    "auth_failed",
    "authentication_failed",
    "authorization_failed",
    "invalid_password",
    "security_mismatch",
}

PERMANENT_PAYLOAD_ERROR_CODES = {
    "invalid_command_payload",
    "unsupported_intent",
    "unsupported_obis",
    "validation_error",
}


def post_process_runtime_outcome(
    *,
    result: RuntimeCommandResult,
    session_result: RuntimeSessionResult | None,
    ingestion_result: RuntimeIngestionPersistenceResult,
    attempt: CommandExecutionAttempt,
    command: MeterCommand,
) -> RuntimePostProcessingResult:
    outcome_category = _classify_outcome(
        result=result,
        session_result=session_result,
        ingestion_result=ingestion_result,
    )
    retry = _build_retry_decision(
        outcome_category=outcome_category,
        latest_error_code=result.latest_error_code,
        command=command,
    )
    signals = RuntimeDownstreamSignals(
        should_retry=retry.should_retry,
        should_schedule_followup=outcome_category == RuntimeOutcomeCategory.PARTIAL_SUCCESS,
        should_raise_operational_event=outcome_category
        in {
            RuntimeOutcomeCategory.RETRYABLE_FAILURE,
            RuntimeOutcomeCategory.PERMANENT_FAILURE,
            RuntimeOutcomeCategory.PARTIAL_SUCCESS,
            RuntimeOutcomeCategory.TIMEOUT,
        },
        should_mark_endpoint_unhealthy=outcome_category
        in {
            RuntimeOutcomeCategory.RETRYABLE_FAILURE,
            RuntimeOutcomeCategory.TIMEOUT,
        },
    )
    summary = {
        "outcome_category": outcome_category.value,
        "retry": retry.model_dump(),
        "signals": signals.model_dump(),
        "attempt_number": attempt.attempt_number,
        "command_retry_state": {
            "current_retry_count": command.retry_count,
            "max_retries": command.max_retries,
        },
    }
    return RuntimePostProcessingResult(
        outcome_category=outcome_category,
        retry=retry,
        signals=signals,
        summary=summary,
    )


def _classify_outcome(
    *,
    result: RuntimeCommandResult,
    session_result: RuntimeSessionResult | None,
    ingestion_result: RuntimeIngestionPersistenceResult,
) -> RuntimeOutcomeCategory:
    if result.outcome == RuntimeCommandOutcome.SUCCEEDED:
        return RuntimeOutcomeCategory.SUCCESS
    if result.outcome == RuntimeCommandOutcome.TIMED_OUT:
        return RuntimeOutcomeCategory.TIMEOUT
    if result.outcome == RuntimeCommandOutcome.PARTIAL:
        return RuntimeOutcomeCategory.PARTIAL_SUCCESS

    error_code = (result.latest_error_code or "").strip().lower()
    if error_code in TRANSPORT_RETRYABLE_ERROR_CODES:
        return RuntimeOutcomeCategory.RETRYABLE_FAILURE
    if error_code in PERMANENT_AUTH_ERROR_CODES or error_code in PERMANENT_PAYLOAD_ERROR_CODES:
        return RuntimeOutcomeCategory.PERMANENT_FAILURE

    if session_result is not None and session_result.status.value == "timed_out":
        return RuntimeOutcomeCategory.TIMEOUT
    if (
        result.outcome == RuntimeCommandOutcome.FAILED
        and ingestion_result.ingested_batch is not None
        and (
            ingestion_result.ingested_batch.readings
            or ingestion_result.ingested_batch.register_snapshots
            or ingestion_result.persisted_interval_count > 0
        )
    ):
        return RuntimeOutcomeCategory.PARTIAL_SUCCESS
    return RuntimeOutcomeCategory.PERMANENT_FAILURE


def _build_retry_decision(
    *,
    outcome_category: RuntimeOutcomeCategory,
    latest_error_code: str | None,
    command: MeterCommand,
) -> RuntimeRetryPolicyDecision:
    retry_allowed_by_policy = outcome_category in {
        RuntimeOutcomeCategory.RETRYABLE_FAILURE,
        RuntimeOutcomeCategory.TIMEOUT,
    }
    retry_possible_by_budget = command.retry_count < command.max_retries
    should_retry = retry_allowed_by_policy and retry_possible_by_budget
    return RuntimeRetryPolicyDecision(
        retry_allowed_by_policy=retry_allowed_by_policy,
        retry_possible_by_budget=retry_possible_by_budget,
        should_retry=should_retry,
        retry_delay_seconds=0 if should_retry else 0,
        reason=_build_retry_reason(
            outcome_category=outcome_category,
            latest_error_code=latest_error_code,
            should_retry=should_retry,
            retry_possible_by_budget=retry_possible_by_budget,
        ),
    )


def _build_retry_reason(
    *,
    outcome_category: RuntimeOutcomeCategory,
    latest_error_code: str | None,
    should_retry: bool,
    retry_possible_by_budget: bool,
) -> str:
    if should_retry:
        return f"Policy allows retry for {outcome_category.value}."
    if outcome_category in {RuntimeOutcomeCategory.SUCCESS, RuntimeOutcomeCategory.PARTIAL_SUCCESS}:
        return "No retry required."
    if not retry_possible_by_budget:
        return "Retry budget exhausted."
    if latest_error_code:
        return f"Policy marked error code '{latest_error_code}' as non-retryable."
    return f"Policy marked outcome '{outcome_category.value}' as non-retryable."
