from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.schemas import (
    CurrentRoleSummary,
    CurrentUserResponse,
    LoginResponse,
    PermissionSummary,
)
from app.modules.auth.security import create_access_token, verify_password
from app.modules.users.enums import UserStatus
from app.modules.users.models import User
from app.modules.users.service import get_user_by_identifier, resolve_permission_codes


def authenticate_user(session: Session, *, username_or_email: str, password: str) -> User:
    user = get_user_by_identifier(session, username_or_email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    user.last_login_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def issue_access_token_for_user(user: User) -> LoginResponse:
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(subject=user.id, expires_delta=expires_delta)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(expires_delta.total_seconds()),
        user=build_current_user_response(user),
    )


def build_current_user_response(user: User) -> CurrentUserResponse:
    permissions = sorted(resolve_permission_codes(user))
    roles = sorted(
        user.role_assignments,
        key=lambda assignment: (assignment.role.name, assignment.scope_type, assignment.scope_identifier),
    )
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        status=user.status.value,
        is_superuser=user.is_superuser,
        roles=[
            CurrentRoleSummary(
                id=assignment.role.id,
                code=assignment.role.code,
                name=assignment.role.name,
                scope_type=assignment.scope_type,
                scope_identifier=assignment.scope_identifier,
            )
            for assignment in roles
        ],
        permissions=[PermissionSummary(code=code) for code in permissions],
    )
