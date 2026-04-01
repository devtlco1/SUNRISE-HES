from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings
from app.modules.auth.schemas import TokenPayload

logger = logging.getLogger(__name__)
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, password_hash_value: str) -> bool:
    try:
        return password_hash.verify(password, password_hash_value)
    except Exception:
        logger.warning("Password verification failed because the stored hash is invalid.")
        return False


def create_access_token(*, subject: UUID, expires_delta: timedelta | None = None) -> str:
    issued_at = datetime.now(UTC)
    expires_at = issued_at + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": str(subject),
        "type": "access",
        "iss": settings.jwt_issuer,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
        )
    except InvalidTokenError as exc:
        raise ValueError("Invalid access token.") from exc

    token_payload = TokenPayload.model_validate(payload)
    if token_payload.token_type != "access":
        raise ValueError("Unsupported token type.")
    return token_payload
