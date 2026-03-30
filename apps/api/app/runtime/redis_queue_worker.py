from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta


def build_worker_consumer_name(worker_identifier: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", worker_identifier.strip().lower()).strip("-")
    return f"hes-worker:{normalized or 'default'}"


def build_claim_token(
    *,
    consumer_group: str,
    consumer_name: str,
    message_id: str,
    claim_timeout_seconds: int,
) -> str:
    lease_expires_at = datetime.now(UTC) + timedelta(seconds=claim_timeout_seconds)
    lease_window = lease_expires_at.strftime("%Y%m%d%H%M%S")
    return f"redis-claim:{consumer_group}:{consumer_name}:{message_id}:{lease_window}"


def claim_token_matches(
    *,
    claim_token: str,
    consumer_name: str,
    message_id: str,
) -> bool:
    return (
        claim_token.startswith("redis-claim:")
        and consumer_name in claim_token
        and f":{message_id}:" in claim_token
    )
