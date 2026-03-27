from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.auth.security import hash_password
from app.modules.users.constants import DEFAULT_PERMISSION_DEFINITIONS
from app.modules.users.models import Permission, Role, RolePermission, User, UserRoleAssignment
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


def _user_access_options():
    return (
        selectinload(User.role_assignments)
        .selectinload(UserRoleAssignment.role)
        .selectinload(Role.permissions)
        .selectinload(RolePermission.permission)
    )


def _role_access_options():
    return selectinload(Role.permissions).selectinload(RolePermission.permission)


def get_user_by_identifier(session: Session, identifier: str) -> User | None:
    normalized = identifier.strip().lower()
    statement = (
        select(User)
        .options(_user_access_options())
        .where(or_(func.lower(User.username) == normalized, func.lower(User.email) == normalized))
    )
    return session.scalar(statement)


def get_user_by_id(session: Session, user_id: uuid.UUID) -> User:
    statement = select(User).options(_user_access_options()).where(User.id == user_id)
    user = session.scalar(statement)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


def list_users(session: Session, *, offset: int = 0, limit: int = 50) -> UserListResponse:
    total = session.scalar(select(func.count()).select_from(User)) or 0
    statement = (
        select(User)
        .options(_user_access_options())
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    users = session.scalars(statement).unique().all()
    return UserListResponse(total=total, items=[serialize_user(user) for user in users])


def create_user(session: Session, payload: UserCreate) -> User:
    existing_user = session.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == payload.username.strip().lower(),
                func.lower(User.email) == payload.email.lower(),
            )
        )
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that username or email already exists.",
        )

    user = User(
        username=payload.username.strip().lower(),
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        status=payload.status,
        is_superuser=payload.is_superuser,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return get_user_by_id(session, user.id)


def create_role(session: Session, payload: RoleCreate) -> Role:
    existing_role = session.scalar(select(Role).where(func.lower(Role.code) == payload.code.lower()))
    if existing_role is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A role with that code already exists.",
        )

    permission_codes = sorted(set(payload.permission_codes))
    permissions = list_permissions_by_codes(session, permission_codes) if permission_codes else []
    if permission_codes and len(permissions) != len(permission_codes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more permission codes are invalid.",
        )

    role = Role(
        code=payload.code.strip().lower(),
        name=payload.name.strip(),
        description=payload.description,
    )
    session.add(role)
    session.flush()

    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission_id=permission.id))

    session.commit()
    session.refresh(role)
    return get_role_by_id(session, role.id)


def get_role_by_id(session: Session, role_id: uuid.UUID) -> Role:
    statement = select(Role).options(_role_access_options()).where(Role.id == role_id)
    role = session.scalar(statement)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    return role


def list_roles(session: Session) -> RoleListResponse:
    total = session.scalar(select(func.count()).select_from(Role)) or 0
    roles = session.scalars(select(Role).options(_role_access_options()).order_by(Role.name.asc())).unique().all()
    return RoleListResponse(total=total, items=[serialize_role(role) for role in roles])


def list_permissions(session: Session) -> list[PermissionResponse]:
    permissions = session.scalars(select(Permission).order_by(Permission.resource.asc(), Permission.action.asc())).all()
    return [serialize_permission(permission) for permission in permissions]


def list_permissions_by_codes(session: Session, permission_codes: list[str]) -> list[Permission]:
    if not permission_codes:
        return []
    statement = select(Permission).where(Permission.code.in_(permission_codes))
    return session.scalars(statement).all()


def assign_role_to_user(
    session: Session,
    *,
    user_id: uuid.UUID,
    payload: UserRoleAssignmentRequest,
    assigned_by_user_id: uuid.UUID | None,
) -> UserRoleAssignment:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    role = session.get(Role, payload.role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    existing_assignment = session.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == payload.role_id,
            UserRoleAssignment.scope_type == payload.scope_type,
            UserRoleAssignment.scope_identifier == payload.scope_identifier,
        )
    )
    if existing_assignment is not None:
        return existing_assignment

    assignment = UserRoleAssignment(
        user_id=user_id,
        role_id=payload.role_id,
        scope_type=payload.scope_type,
        scope_identifier=payload.scope_identifier,
        assigned_by_user_id=assigned_by_user_id,
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return assignment


def ensure_default_permissions(session: Session) -> list[Permission]:
    created_permissions: list[Permission] = []
    for definition in DEFAULT_PERMISSION_DEFINITIONS:
        permission = session.scalar(select(Permission).where(Permission.code == definition["code"]))
        if permission is None:
            permission = Permission(**definition)
            session.add(permission)
            created_permissions.append(permission)
    session.flush()
    return created_permissions


def get_permissions_for_user(user: User) -> list[Permission]:
    permission_map: dict[str, Permission] = {}
    for assignment in user.role_assignments:
        for role_permission in assignment.role.permissions:
            permission = role_permission.permission
            permission_map[permission.code] = permission
    return sorted(permission_map.values(), key=lambda permission: permission.code)


def resolve_permission_codes(user: User) -> set[str]:
    codes = {permission.code for permission in get_permissions_for_user(user)}
    if user.is_superuser:
        codes.update(permission["code"] for permission in DEFAULT_PERMISSION_DEFINITIONS)
    return codes


def serialize_permission(permission: Permission) -> PermissionResponse:
    return PermissionResponse(
        id=permission.id,
        code=permission.code,
        resource=permission.resource,
        action=permission.action,
        description=permission.description,
    )


def serialize_role(role: Role) -> RoleResponse:
    permissions = sorted(
        [serialize_permission(role_permission.permission) for role_permission in role.permissions],
        key=lambda item: item.code,
    )
    return RoleResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=permissions,
    )


def serialize_user(user: User) -> UserResponse:
    assignments = sorted(
        user.role_assignments,
        key=lambda assignment: (assignment.role.name, assignment.scope_type, assignment.scope_identifier),
    )
    permission_objects = get_permissions_for_user(user)
    if user.is_superuser:
        permission_objects_by_code = {permission.code: permission for permission in permission_objects}
        for definition in DEFAULT_PERMISSION_DEFINITIONS:
            permission = permission_objects_by_code.get(definition["code"])
            if permission is not None:
                continue
            permission_objects.append(
                Permission(
                    id=uuid.uuid4(),
                    code=definition["code"],
                    resource=definition["resource"],
                    action=definition["action"],
                    description=definition["description"],
                )
            )
        permission_objects = sorted(permission_objects, key=lambda permission: permission.code)
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        status=user.status,
        is_superuser=user.is_superuser,
        roles=[
            UserRoleAssignmentResponse(
                id=assignment.id,
                role_id=assignment.role_id,
                role_code=assignment.role.code,
                role_name=assignment.role.name,
                scope_type=assignment.scope_type,
                scope_identifier=assignment.scope_identifier,
            )
            for assignment in assignments
        ],
        permissions=[serialize_permission(permission) for permission in permission_objects],
    )
