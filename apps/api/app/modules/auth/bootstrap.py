from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.auth.security import hash_password, verify_password
from app.modules.users.enums import UserStatus
from app.modules.users.constants import DEFAULT_PERMISSION_DEFINITIONS, DEFAULT_ROLE_DEFINITIONS
from app.modules.users.models import Permission, Role, RolePermission, User, UserRoleAssignment
from app.modules.users.schemas import UserCreate, UserRoleAssignmentRequest
from app.modules.users.service import assign_role_to_user, create_user, ensure_default_permissions

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    permissions_created: int
    roles_created: int
    super_admin_created: bool
    super_admin_assigned: bool


def _get_bootstrap_super_admin(session: Session, *, username: str, email: str) -> User | None:
    user_by_username = session.scalar(
        select(User).where(func.lower(User.username) == username.strip().lower())
    )
    user_by_email = session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))

    if user_by_username is not None and user_by_email is not None:
        if user_by_username.id != user_by_email.id:
            raise RuntimeError(
                "Bootstrap super-admin configuration matches different existing users by "
                "username and email."
            )
        return user_by_username

    return user_by_username or user_by_email


def bootstrap_access_control(session: Session) -> BootstrapResult:
    created_permissions = ensure_default_permissions(session)

    permissions_by_code = {
        permission.code: permission
        for permission in session.scalars(select(Permission)).all()
    }
    roles_created = 0
    for role_definition in DEFAULT_ROLE_DEFINITIONS:
        role = session.scalar(select(Role).where(Role.code == role_definition["code"]))
        if role is None:
            role = Role(
                code=role_definition["code"],
                name=role_definition["name"],
                description=role_definition["description"],
                is_system=role_definition["is_system"],
            )
            session.add(role)
            session.flush()
            roles_created += 1

        existing_permission_ids = {
            role_permission.permission_id
            for role_permission in session.scalars(
                select(RolePermission).where(RolePermission.role_id == role.id)
            ).all()
        }
        for permission_code in role_definition["permission_codes"]:
            permission = permissions_by_code[permission_code]
            if permission.id not in existing_permission_ids:
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))

    session.commit()

    super_admin_created = False
    super_admin_assigned = False
    username = settings.bootstrap_super_admin_username
    email = settings.bootstrap_super_admin_email
    password = settings.bootstrap_super_admin_password

    if username and email and password:
        super_admin = _get_bootstrap_super_admin(session, username=username, email=email)
        if super_admin is None:
            super_admin = create_user(
                session,
                UserCreate(
                    username=username,
                    email=email,
                    full_name=settings.bootstrap_super_admin_full_name,
                    password=password,
                    is_superuser=True,
                ),
            )
            super_admin_created = True
        else:
            normalized_username = username.strip().lower()
            normalized_email = email.strip().lower()
            bootstrap_changed = False
            if super_admin.username != normalized_username:
                super_admin.username = normalized_username
                bootstrap_changed = True
            if super_admin.email != normalized_email:
                super_admin.email = normalized_email
                bootstrap_changed = True
            if super_admin.full_name != settings.bootstrap_super_admin_full_name.strip():
                super_admin.full_name = settings.bootstrap_super_admin_full_name.strip()
                bootstrap_changed = True
            if super_admin.status != UserStatus.ACTIVE:
                super_admin.status = UserStatus.ACTIVE
                bootstrap_changed = True
            if not super_admin.is_superuser:
                super_admin.is_superuser = True
                bootstrap_changed = True
            if not verify_password(password, super_admin.password_hash):
                super_admin.password_hash = hash_password(password)
                bootstrap_changed = True
            if bootstrap_changed:
                session.add(super_admin)
                session.commit()
                session.refresh(super_admin)

        super_admin_role = session.scalar(select(Role).where(Role.code == "super_admin"))
        assert super_admin_role is not None
        existing_assignment = session.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == super_admin.id,
                UserRoleAssignment.role_id == super_admin_role.id,
                UserRoleAssignment.scope_type == "platform",
                UserRoleAssignment.scope_identifier == "global",
            )
        )
        if existing_assignment is None:
            assign_role_to_user(
                session,
                user_id=super_admin.id,
                payload=UserRoleAssignmentRequest(role_id=super_admin_role.id),
                assigned_by_user_id=super_admin.id,
            )
            super_admin_assigned = True
    elif username or email or password:
        logger.warning(
            "Bootstrap super-admin configuration is incomplete. "
            "Username, email, and password must all be set."
        )

    return BootstrapResult(
        permissions_created=len(created_permissions),
        roles_created=roles_created,
        super_admin_created=super_admin_created,
        super_admin_assigned=super_admin_assigned,
    )


def main() -> None:
    with SessionLocal() as session:
        result = bootstrap_access_control(session)
    print(
        "Bootstrap completed: "
        f"permissions_seeded={result.permissions_created}, "
        f"roles_created={result.roles_created}, "
        f"super_admin_created={result.super_admin_created}, "
        f"super_admin_assigned={result.super_admin_assigned}"
    )


if __name__ == "__main__":
    main()
