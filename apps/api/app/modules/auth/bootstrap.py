from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.users.constants import DEFAULT_PERMISSION_DEFINITIONS, DEFAULT_ROLE_DEFINITIONS
from app.modules.users.models import Permission, Role, RolePermission, User, UserRoleAssignment
from app.modules.users.schemas import UserCreate, UserRoleAssignmentRequest
from app.modules.users.service import assign_role_to_user, create_user, ensure_default_permissions


@dataclass
class BootstrapResult:
    permissions_created: int
    roles_created: int
    super_admin_created: bool
    super_admin_assigned: bool


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
        super_admin = session.scalar(select(User).where(User.username == username.lower()))
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
