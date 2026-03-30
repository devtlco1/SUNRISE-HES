from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerLedgerClosureSummary(StringEnum):
    LEDGER_CLOSURE_SUMMARY = "ledger_closure_summary"
    ARCHIVAL_ACTION_RECORD = "archival_action_record"
    CLOSURE_NOTE = "closure_note"
    ARCHIVAL_PROOF_ARTIFACT = "archival_proof_artifact"
    NOOP_LEDGER_CLOSURE = "noop_ledger_closure"


class RedisWorkerLedgerClosureRecord(BaseModel):
    closure_type: RedisWorkerLedgerClosureSummary
    detail: str
    terminal: bool


class RedisWorkerArchivalArtifact(BaseModel):
    records: list[RedisWorkerLedgerClosureRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    closure_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
