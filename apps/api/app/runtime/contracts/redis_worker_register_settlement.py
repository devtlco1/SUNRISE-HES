from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerRegisterSettlementSummary(StringEnum):
    REGISTER_SETTLEMENT_SUMMARY = "register_settlement_summary"
    SETTLEMENT_ACTION_RECORD = "settlement_action_record"
    REGISTER_SETTLEMENT_NOTE = "register_settlement_note"
    POST_COMPLETION_SETTLEMENT_ARTIFACT = "post_completion_settlement_artifact"
    NOOP_REGISTER_SETTLEMENT = "noop_register_settlement"


class RedisWorkerRegisterSettlementRecord(BaseModel):
    settlement_type: RedisWorkerRegisterSettlementSummary
    detail: str
    terminal: bool


class RedisWorkerSettlementArtifact(BaseModel):
    records: list[RedisWorkerRegisterSettlementRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    settlement_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
