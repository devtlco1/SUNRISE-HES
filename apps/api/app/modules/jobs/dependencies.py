from fastapi import Header, HTTPException, status

from app.core.config import settings

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def require_internal_api_token(
    x_internal_token: str | None = Header(default=None, alias=INTERNAL_TOKEN_HEADER),
) -> None:
    if x_internal_token != settings.internal_api_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API token.",
        )
