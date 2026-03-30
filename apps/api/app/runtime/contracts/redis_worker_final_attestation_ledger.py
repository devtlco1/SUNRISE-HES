from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerFinalAttestationLedgerSummary(StringEnum):
    FINAL_ATTESTATION_LEDGER_SUMMARY = "final_attestation_ledger_summary"
    LEDGER_ACTION_RECORD = "ledger_action_record"
    NOTARIZATION_NOTE = "notarization_note"
    FINAL_LEDGER_ARTIFACT = "final_ledger_artifact"
    NOOP_FINAL_ATTESTATION_LEDGER = "noop_final_attestation_ledger"


class RedisWorkerFinalAttestationLedgerRecord(BaseModel):
    ledger_type: RedisWorkerFinalAttestationLedgerSummary
    detail: str
    terminal: bool


class RedisWorkerNotarizationArtifact(BaseModel):
    records: list[RedisWorkerFinalAttestationLedgerRecord] = Field(default_factory=list)
    total_records: int = 0
    terminal_records: int = 0
    ledger_ready: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
