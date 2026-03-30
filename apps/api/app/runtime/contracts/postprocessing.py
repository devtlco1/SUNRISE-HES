from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum


class RuntimeOutcomeCategory(StringEnum):
    SUCCESS = "success"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"
    TIMEOUT = "timeout"
    PARTIAL_SUCCESS = "partial_success"


class RuntimeRetryPolicyDecision(BaseModel):
    retry_allowed_by_policy: bool
    retry_possible_by_budget: bool
    should_retry: bool
    retry_delay_seconds: int
    reason: str


class RuntimeDownstreamSignals(BaseModel):
    should_retry: bool
    should_schedule_followup: bool
    should_raise_operational_event: bool
    should_mark_endpoint_unhealthy: bool


class RuntimePostProcessingResult(BaseModel):
    outcome_category: RuntimeOutcomeCategory
    retry: RuntimeRetryPolicyDecision
    signals: RuntimeDownstreamSignals
    summary: dict[str, object]
