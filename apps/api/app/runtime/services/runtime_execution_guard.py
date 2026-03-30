from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.runtime.contracts import (
    RuntimeExecutionGuardResult,
    RuntimeExecutionInvocationGateResult,
    RuntimeExecutionLeaseResult,
)


def build_runtime_execution_guard_metadata(
    *,
    execution_metadata: dict[str, object] | None,
    executor_identifier: str,
    attempt_id: str,
) -> dict[str, object]:
    lease = _load_runtime_execution_lease(execution_metadata)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution requires an active runtime lease.",
        )
    _ensure_lease_matches_executor(lease=lease, executor_identifier=executor_identifier)
    _ensure_lease_is_active(lease)

    invocation = _load_runtime_execution_invocation(execution_metadata)
    if invocation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution requires an active runtime invocation gate.",
        )
    _ensure_invocation_matches_executor(
        invocation=invocation,
        executor_identifier=executor_identifier,
    )
    _ensure_invocation_is_active(invocation)
    lease_expires_at = datetime.fromisoformat(lease.lease_expires_at)
    invocation_expires_at = datetime.fromisoformat(invocation.gate_expires_at)
    if invocation.lineage.lease_record_id != lease.lease_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate does not match the active runtime lease.",
        )

    guard = RuntimeExecutionGuardResult(
        guard_record_id=f"runtime-execution-guard:{attempt_id}:{executor_identifier}",
        executor_identifier=executor_identifier,
        attempt_id=attempt_id,
        lease_record_id=lease.lease_record_id,
        invocation_record_id=invocation.invocation_record_id,
        execution_started_at=datetime.now(UTC).isoformat(),
        guard_expires_at=min(lease_expires_at, invocation_expires_at).isoformat(),
        dispatch_request_identity=lease.lineage.dispatch_request_identity,
        queue_message_id=lease.lineage.queue_message_id,
        claim_token=lease.lineage.claim_token,
    )
    return {"runtime_execution_guard": guard.model_dump(mode="json")}


def _load_runtime_execution_lease(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionLeaseResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_lease")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionLeaseResult.model_validate(payload)


def _load_runtime_execution_invocation(
    execution_metadata: dict[str, object] | None,
) -> RuntimeExecutionInvocationGateResult | None:
    if not isinstance(execution_metadata, dict):
        return None
    payload = execution_metadata.get("runtime_execution_invocation_gate")
    if not isinstance(payload, dict):
        return None
    return RuntimeExecutionInvocationGateResult.model_validate(payload)


def _ensure_lease_matches_executor(
    *,
    lease: RuntimeExecutionLeaseResult,
    executor_identifier: str,
) -> None:
    if lease.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is owned by another executor.",
        )


def _ensure_lease_is_active(lease: RuntimeExecutionLeaseResult) -> None:
    try:
        lease_expires_at = datetime.fromisoformat(lease.lease_expires_at)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is invalid and cannot authorize execution.",
        ) from exc
    if lease_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution lease is expired and cannot authorize execution.",
        )


def _ensure_invocation_matches_executor(
    *,
    invocation: RuntimeExecutionInvocationGateResult,
    executor_identifier: str,
) -> None:
    if invocation.executor_identifier != executor_identifier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate is owned by another executor.",
        )


def _ensure_invocation_is_active(invocation: RuntimeExecutionInvocationGateResult) -> None:
    try:
        gate_expires_at = datetime.fromisoformat(invocation.gate_expires_at)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate is invalid and cannot authorize execution.",
        ) from exc
    if gate_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime execution invocation gate is expired and cannot authorize execution.",
        )
