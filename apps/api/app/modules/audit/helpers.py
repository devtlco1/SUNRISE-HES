from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "password_secret_ref",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "set-cookie",
    "secret",
    "secret_ref",
    "auth_key_ref",
    "block_cipher_key_ref",
    "dedicated_key_ref",
}


def scrub_sensitive_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): ("***redacted***" if str(key).lower() in SENSITIVE_KEYS else scrub_sensitive_data(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return [scrub_sensitive_data(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def build_audit_payload(*, outcome: str, context_details: dict[str, Any], details: dict[str, Any] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "outcome": outcome,
        "http": scrub_sensitive_data(context_details),
    }
    if details:
        payload["details"] = scrub_sensitive_data(details)
    return payload
