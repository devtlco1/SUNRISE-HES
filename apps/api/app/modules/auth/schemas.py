from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=255)


class TokenPayload(BaseModel):
    sub: UUID
    token_type: str = Field(alias="type")
    iss: str
    iat: int
    exp: int

    model_config = ConfigDict(populate_by_name=True)


class PermissionSummary(BaseModel):
    code: str


class CurrentRoleSummary(BaseModel):
    id: UUID
    code: str
    name: str
    scope_type: str
    scope_identifier: str


class CurrentUserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: str
    status: str
    is_superuser: bool
    roles: list[CurrentRoleSummary]
    permissions: list[PermissionSummary]

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: CurrentUserResponse
