from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerControlPlaneSummary(StringEnum):
    CONTROL_PLANE_SUMMARY = "control_plane_summary"
    APPROVAL_REQUIRED_RECORD = "approval_required_record"
    BROKER_OPERATIONS_NOTE = "broker_operations_note"
    CONTROL_REVIEW_ARTIFACT = "control_review_artifact"
    NOOP_CONTROL_PLANE = "noop_control_plane"


class RedisWorkerControlPlaneRecord(BaseModel):
    control_type: RedisWorkerControlPlaneSummary
    detail: str
    terminal: bool


class RedisWorkerApprovalArtifact(BaseModel):
    records: list[RedisWorkerControlPlaneRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    approval_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
