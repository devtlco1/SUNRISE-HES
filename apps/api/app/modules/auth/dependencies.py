from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.context import attach_actor_to_context
from app.modules.auth.security import decode_access_token
from app.modules.users.enums import UserStatus
from app.modules.users.models import User
from app.modules.users.service import get_user_by_id, resolve_permission_codes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_db_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = UUID(str(payload.sub))
        user = get_user_by_id(session, user_id)
    except (HTTPException, ValueError, TypeError) as exc:
        raise credentials_exception from exc

    attach_actor_to_context(user.id)
    if hasattr(request.state, "request_audit_context"):
        request.state.request_audit_context = replace(
            request.state.request_audit_context,
            actor_user_id=user.id,
        )
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive users cannot access this resource.",
        )
    return current_user


def require_permission(permission_code: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        permissions = resolve_permission_codes(current_user)
        if current_user.is_superuser or permission_code in permissions:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {permission_code}",
        )

    return dependency
