from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.service import record_audit_event
from app.modules.auth.dependencies import require_permission
from app.modules.auth.schemas import CurrentUserResponse, LoginRequest, LoginResponse
from app.modules.auth.service import authenticate_user, build_current_user_response, issue_access_token_for_user
from app.modules.users.models import User
from app.modules.users.service import get_user_by_identifier

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> LoginResponse:
    try:
        user = authenticate_user(
            session,
            username_or_email=payload.username_or_email,
            password=payload.password,
        )
    except HTTPException as exc:
        existing_user = get_user_by_identifier(session, payload.username_or_email)
        record_audit_event(
            session,
            action="auth.login.failed",
            resource_type="auth",
            actor_user_id=existing_user.id if existing_user is not None else None,
            outcome="failure",
            description="Authentication attempt failed.",
            details={
                "username_or_email": payload.username_or_email,
                "reason": exc.detail,
            },
            request_context=request.state.request_audit_context,
        )
        raise

    response = issue_access_token_for_user(user)
    record_audit_event(
        session,
        action="auth.login.success",
        resource_type="auth",
        actor_user_id=user.id,
        outcome="success",
        description="Authentication succeeded.",
        details={"username": user.username},
        request_context=request.state.request_audit_context,
    )
    return response


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("auth.me")),
) -> CurrentUserResponse:
    response = build_current_user_response(current_user)
    record_audit_event(
        session,
        action="auth.me.read",
        resource_type="users",
        resource_id=current_user.id,
        actor_user_id=current_user.id,
        outcome="success",
        description="Current user profile retrieved.",
        details={"username": current_user.username},
        request_context=request.state.request_audit_context,
    )
    return response
