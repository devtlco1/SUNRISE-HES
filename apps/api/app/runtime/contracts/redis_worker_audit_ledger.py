from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum


class RedisWorkerAuditLedger(StringEnum):
    AUDIT_LEDGER_ENTRY = "audit_ledger_entry"
    VERIFICATION_RECORD = "verification_record"
    COMPLIANCE_READY_ENTRY = "compliance_ready_entry"
    RECONCILIATION_HISTORY_ENTRY = "reconciliation_history_entry"
    NOOP_AUDIT_LEDGER = "noop_audit_ledger"


class RedisWorkerAuditLedgerEntry(BaseModel):
    entry_type: RedisWorkerAuditLedger
    detail: str
    terminal: bool


class RedisWorkerVerificationRecord(BaseModel):
    ledger_entries: list[RedisWorkerAuditLedgerEntry] = Field(default_factory=list)
    total_entries: int = 0
    terminal_entries: int = 0
    verified: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)
