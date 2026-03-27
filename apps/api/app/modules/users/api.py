import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.service import record_audit_event
from app.modules.auth.dependencies import require_permission
from app.modules.users.models import User
from app.modules.users.schemas import (
    PermissionResponse,
    RoleCreate,
    RoleListResponse,
    RoleResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRoleAssignmentRequest,
    UserRoleAssignmentResponse,
)
from app.modules.users.service import (
    assign_role_to_user,
    create_role,
    create_user,
    get_role_by_id,
    get_user_by_id,
    list_permissions,
    list_roles,
    list_users,
    serialize_role,
    serialize_user,
)

users_router = APIRouter(prefix="/users", tags=["users"])
roles_router = APIRouter(prefix="/roles", tags=["roles"])
permissions_router = APIRouter(prefix="/permissions", tags=["permissions"])


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("users.write")),
) -> UserResponse:
    user = create_user(session, payload)
    response = serialize_user(user)
    record_audit_event(
        session,
        action="users.create",
        resource_type="users",
        resource_id=user.id,
        actor_user_id=current_user.id,
        outcome="success",
        description="User created.",
        details={"username": user.username, "email": user.email},
        request_context=request.state.request_audit_context,
    )
    return response


@users_router.get("", response_model=UserListResponse)
def list_users_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("users.read")),
) -> UserListResponse:
    return list_users(session, offset=offset, limit=limit)


@users_router.get("/{user_id}", response_model=UserResponse)
def get_user_endpoint(
    user_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("users.read")),
) -> UserResponse:
    user = get_user_by_id(session, user_id)
    return serialize_user(user)


@users_router.post("/{user_id}/roles", response_model=UserRoleAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_role_endpoint(
    user_id: uuid.UUID,
    payload: UserRoleAssignmentRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("roles.write")),
) -> UserRoleAssignmentResponse:
    assignment = assign_role_to_user(
        session,
        user_id=user_id,
        payload=payload,
        assigned_by_user_id=current_user.id,
    )
    role = get_role_by_id(session, assignment.role_id)
    response = UserRoleAssignmentResponse(
        id=assignment.id,
        role_id=assignment.role_id,
        role_code=role.code,
        role_name=role.name,
        scope_type=assignment.scope_type,
        scope_identifier=assignment.scope_identifier,
    )
    record_audit_event(
        session,
        action="users.roles.assign",
        resource_type="user_role_assignments",
        resource_id=assignment.id,
        actor_user_id=current_user.id,
        outcome="success",
        description="Role assigned to user.",
        details={
            "assigned_user_id": str(user_id),
            "role_id": str(assignment.role_id),
            "scope_type": assignment.scope_type,
            "scope_identifier": assignment.scope_identifier,
        },
        request_context=request.state.request_audit_context,
    )
    return response


@roles_router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role_endpoint(
    payload: RoleCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("roles.write")),
) -> RoleResponse:
    role = create_role(session, payload)
    response = serialize_role(role)
    record_audit_event(
        session,
        action="roles.create",
        resource_type="roles",
        resource_id=role.id,
        actor_user_id=current_user.id,
        outcome="success",
        description="Role created.",
        details={"code": role.code, "permission_codes": payload.permission_codes},
        request_context=request.state.request_audit_context,
    )
    return response


@roles_router.get("", response_model=RoleListResponse)
def list_roles_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("roles.read")),
) -> RoleListResponse:
    return list_roles(session)


@permissions_router.get("", response_model=list[PermissionResponse])
def list_permissions_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("roles.read")),
) -> list[PermissionResponse]:
    return list_permissions(session)
