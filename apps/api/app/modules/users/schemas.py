from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.enums import UserStatus


class PermissionResponse(BaseModel):
    id: UUID
    code: str
    resource: str
    action: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=3, max_length=128)
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)


class RoleResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[PermissionResponse]


class RoleListResponse(BaseModel):
    total: int
    items: list[RoleResponse]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=255)
    status: UserStatus = UserStatus.ACTIVE
    is_superuser: bool = False


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=255)
    email: EmailStr | None = None
    status: UserStatus | None = None
    is_superuser: bool | None = None


class UserRoleAssignmentRequest(BaseModel):
    role_id: UUID
    scope_type: str = Field(default="platform", min_length=1, max_length=64)
    scope_identifier: str = Field(default="global", min_length=1, max_length=128)


class UserRoleAssignmentResponse(BaseModel):
    id: UUID
    role_id: UUID
    role_code: str
    role_name: str
    scope_type: str
    scope_identifier: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    full_name: str
    status: UserStatus
    is_superuser: bool
    roles: list[UserRoleAssignmentResponse]
    permissions: list[PermissionResponse]


class UserListResponse(BaseModel):
    total: int
    items: list[UserResponse]
