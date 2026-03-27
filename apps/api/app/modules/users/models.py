from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.users.enums import UserStatus


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, name="user_status"),
        nullable=False,
        server_default=UserStatus.ACTIVE.value,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    role_assignments: Mapped[list["UserRoleAssignment"]] = relationship(
        back_populates="user",
        foreign_keys="UserRoleAssignment.user_id",
    )

    __table_args__ = (
        UniqueConstraint("username"),
        UniqueConstraint("email"),
        Index("ix_users_status", "status"),
    )


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role")
    assignments: Mapped[list["UserRoleAssignment"]] = relationship(back_populates="role")

    __table_args__ = (
        UniqueConstraint("code"),
        UniqueConstraint("name"),
    )


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())

    roles: Mapped[list["RolePermission"]] = relationship(back_populates="permission")

    __table_args__ = (
        UniqueConstraint("code"),
        UniqueConstraint("resource", "action"),
    )


class RolePermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="permissions", foreign_keys=[role_id])
    permission: Mapped["Permission"] = relationship(back_populates="roles")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id"),
        Index("ix_role_permissions_permission_id", "permission_id"),
    )


class UserRoleAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_role_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False, server_default="platform")
    scope_identifier: Mapped[str] = mapped_column(String(128), nullable=False, server_default="global")
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    user: Mapped["User"] = relationship(back_populates="role_assignments", foreign_keys=[user_id])
    role: Mapped["Role"] = relationship(back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "scope_type", "scope_identifier"),
        Index("ix_user_role_assignments_role_id", "role_id"),
        Index("ix_user_role_assignments_scope", "scope_type", "scope_identifier"),
    )
