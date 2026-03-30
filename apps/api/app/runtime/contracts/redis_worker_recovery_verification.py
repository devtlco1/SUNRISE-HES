from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRecoveryVerificationSummary(StringEnum):
    RECOVERY_VERIFICATION_SUMMARY = "recovery_verification_summary"
    VERIFICATION_ACTION_RECORD = "verification_action_record"
    RECOVERY_CONFIRMATION_NOTE = "recovery_confirmation_note"
    RESPONSE_CONFIRMATION_ARTIFACT = "response_confirmation_artifact"
    NOOP_RECOVERY_VERIFICATION = "noop_recovery_verification"


class RedisWorkerRecoveryVerificationRecord(BaseModel):
    verification_type: RedisWorkerRecoveryVerificationSummary
    detail: str
    terminal: bool


class RedisWorkerConfirmationArtifact(BaseModel):
    records: list[RedisWorkerRecoveryVerificationRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    confirmation_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
