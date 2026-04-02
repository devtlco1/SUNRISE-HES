from __future__ import annotations

import os
import re


def resolve_runtime_secret_ref(secret_ref: str | None) -> str | None:
    if secret_ref is None:
        return None

    normalized_ref = secret_ref.strip()
    if not normalized_ref:
        return None

    direct_value = os.getenv(normalized_ref)
    if direct_value:
        return direct_value

    fallback_env_name = "RUNTIME_SECRET_" + re.sub(r"[^A-Za-z0-9]", "_", normalized_ref).upper()
    fallback_value = os.getenv(fallback_env_name)
    if fallback_value:
        return fallback_value

    return None

