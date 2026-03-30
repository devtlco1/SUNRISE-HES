from datetime import UTC, datetime
from types import SimpleNamespace

from app.modules.connectivity.enums import ConnectivitySessionPurpose, ConnectivitySessionStatus
from app.runtime.contracts import RuntimeCommandOutcome, RuntimeCommandResult, RuntimeSessionResult
from app.runtime.contracts.postprocessing import RuntimeOutcomeCategory
from app.runtime.services.ingestion import RuntimeIngestionPersistenceResult
from app.runtime.services.postprocessing import post_process_runtime_outcome


def test_success_classification() -> None:
    result = RuntimeCommandResult(outcome=RuntimeCommandOutcome.SUCCEEDED)
    processed = post_process_runtime_outcome(
        result=result,
        session_result=_session_result(ConnectivitySessionStatus.SUCCEEDED),
        ingestion_result=RuntimeIngestionPersistenceResult(),
        attempt=SimpleNamespace(attempt_number=1),
        command=SimpleNamespace(retry_count=0, max_retries=2),
    )

    assert processed.outcome_category == RuntimeOutcomeCategory.SUCCESS
    assert processed.retry.should_retry is False


def test_retryable_failure_classification() -> None:
    result = RuntimeCommandResult(
        outcome=RuntimeCommandOutcome.FAILED,
        latest_error_code="NO_ROUTE",
        latest_error_message="Transport unavailable",
    )
    processed = post_process_runtime_outcome(
        result=result,
        session_result=_session_result(ConnectivitySessionStatus.FAILED),
        ingestion_result=RuntimeIngestionPersistenceResult(),
        attempt=SimpleNamespace(attempt_number=1),
        command=SimpleNamespace(retry_count=0, max_retries=2),
    )

    assert processed.outcome_category == RuntimeOutcomeCategory.RETRYABLE_FAILURE
    assert processed.retry.should_retry is True
    assert processed.signals.should_mark_endpoint_unhealthy is True


def test_permanent_failure_classification() -> None:
    result = RuntimeCommandResult(
        outcome=RuntimeCommandOutcome.FAILED,
        latest_error_code="AUTH_FAILED",
        latest_error_message="Association rejected",
    )
    processed = post_process_runtime_outcome(
        result=result,
        session_result=_session_result(ConnectivitySessionStatus.FAILED),
        ingestion_result=RuntimeIngestionPersistenceResult(),
        attempt=SimpleNamespace(attempt_number=1),
        command=SimpleNamespace(retry_count=0, max_retries=2),
    )

    assert processed.outcome_category == RuntimeOutcomeCategory.PERMANENT_FAILURE
    assert processed.retry.should_retry is False


def test_timeout_classification() -> None:
    result = RuntimeCommandResult(
        outcome=RuntimeCommandOutcome.TIMED_OUT,
        latest_error_code="TIMEOUT",
    )
    processed = post_process_runtime_outcome(
        result=result,
        session_result=_session_result(ConnectivitySessionStatus.TIMED_OUT),
        ingestion_result=RuntimeIngestionPersistenceResult(),
        attempt=SimpleNamespace(attempt_number=1),
        command=SimpleNamespace(retry_count=0, max_retries=1),
    )

    assert processed.outcome_category == RuntimeOutcomeCategory.TIMEOUT
    assert processed.retry.should_retry is True


def test_partial_success_classification() -> None:
    result = RuntimeCommandResult(
        outcome=RuntimeCommandOutcome.PARTIAL,
        latest_error_code="PARTIAL_DATA",
    )
    ingestion_result = RuntimeIngestionPersistenceResult.model_construct(
        ingested_batch=SimpleNamespace(readings=[SimpleNamespace()], register_snapshots=[]),
        ingested_events=[],
        persisted_interval_count=0,
        skipped_duplicate_interval_count=0,
    )
    processed = post_process_runtime_outcome(
        result=result,
        session_result=_session_result(ConnectivitySessionStatus.SUCCEEDED),
        ingestion_result=ingestion_result,
        attempt=SimpleNamespace(attempt_number=1),
        command=SimpleNamespace(retry_count=0, max_retries=1),
    )

    assert processed.outcome_category == RuntimeOutcomeCategory.PARTIAL_SUCCESS
    assert processed.signals.should_schedule_followup is True
    assert processed.retry.should_retry is False


def test_retry_budget_exhaustion_disables_retry() -> None:
    result = RuntimeCommandResult(
        outcome=RuntimeCommandOutcome.FAILED,
        latest_error_code="NO_ROUTE",
    )
    processed = post_process_runtime_outcome(
        result=result,
        session_result=_session_result(ConnectivitySessionStatus.FAILED),
        ingestion_result=RuntimeIngestionPersistenceResult(),
        attempt=SimpleNamespace(attempt_number=2),
        command=SimpleNamespace(retry_count=2, max_retries=2),
    )

    assert processed.outcome_category == RuntimeOutcomeCategory.RETRYABLE_FAILURE
    assert processed.retry.retry_possible_by_budget is False
    assert processed.retry.should_retry is False


def _session_result(status: ConnectivitySessionStatus) -> RuntimeSessionResult:
    now = datetime.now(UTC)
    return RuntimeSessionResult(
        status=status,
        session_purpose=ConnectivitySessionPurpose.MANUAL_DIAGNOSTIC,
        started_at=now,
        ended_at=now,
    )
