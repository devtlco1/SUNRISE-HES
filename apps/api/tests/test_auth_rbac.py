from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.context import REQUEST_ID_HEADER
from app.modules.audit.models import AuditLog
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.users.models import Role, User, UserRoleAssignment
from app.modules.users.schemas import RoleCreate, UserCreate, UserRoleAssignmentRequest
from app.modules.users.service import assign_role_to_user, create_role, create_user


def test_login_success_and_current_user(client, db_session: Session) -> None:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"

    bootstrap_access_control(db_session)

    response = client.post(
        "/api/v1/auth/login",
        headers={REQUEST_ID_HEADER: "req-login-success"},
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["username"] == "admin"
    assert response.headers[REQUEST_ID_HEADER] == "req-login-success"

    audit_log = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "auth.login.success")
    )
    assert audit_log is not None
    assert audit_log.actor_user_id == user_id_from_response(payload["user"]["id"])
    assert audit_log.request_id == "req-login-success"
    assert audit_log.payload["outcome"] == "success"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "admin@example.com"


def test_login_failure_with_invalid_password(client, db_session: Session) -> None:
    bootstrap_access_control(db_session)
    create_user(
        db_session,
        UserCreate(
            username="operator",
            email="operator@example.com",
            full_name="Meter Operator",
            password="SecurePassword123!",
        ),
    )

    response = client.post(
        "/api/v1/auth/login",
        headers={REQUEST_ID_HEADER: "req-login-failure"},
        json={"username_or_email": "operator", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.headers[REQUEST_ID_HEADER] == "req-login-failure"

    audit_log = db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.login.failed"))
    assert audit_log is not None
    assert audit_log.request_id == "req-login-failure"
    assert audit_log.payload["outcome"] == "failure"
    assert audit_log.payload["details"]["username_or_email"] == "operator"


def test_protected_route_requires_permission(client, db_session: Session) -> None:
    bootstrap_access_control(db_session)
    role = create_role(
        db_session,
        RoleCreate(
            code="auth_only",
            name="Auth Only",
            permission_codes=["auth.me"],
        ),
    )
    user = create_user(
        db_session,
        UserCreate(
            username="viewer",
            email="viewer@example.com",
            full_name="Limited Viewer",
            password="SecurePassword123!",
        ),
    )
    assign_role_to_user(
        db_session,
        user_id=user.id,
        payload=UserRoleAssignmentRequest(role_id=role.id),
        assigned_by_user_id=None,
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "viewer", "password": "SecurePassword123!"},
    )
    token = login_response.json()["access_token"]

    users_response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert users_response.status_code == 403
    assert "users.read" in users_response.json()["detail"]


def test_protected_route_requires_authentication(client) -> None:
    response = client.get("/api/v1/users")
    assert response.status_code == 401


def test_create_role_creates_audit_record(client, db_session: Session) -> None:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"
    bootstrap_access_control(db_session)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/roles",
        headers={
            "Authorization": f"Bearer {token}",
            REQUEST_ID_HEADER: "req-create-role",
        },
        json={
            "code": "ops_admin",
            "name": "Operations Admin",
            "description": "Operational admins",
            "permission_codes": ["auth.me", "roles.read"],
        },
    )

    assert response.status_code == 201

    audit_log = db_session.scalar(select(AuditLog).where(AuditLog.action == "roles.create"))
    assert audit_log is not None
    assert audit_log.request_id == "req-create-role"
    assert audit_log.payload["details"]["code"] == "ops_admin"


def test_bootstrap_is_idempotent_and_assigns_super_admin(db_session: Session) -> None:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"

    first_result = bootstrap_access_control(db_session)
    second_result = bootstrap_access_control(db_session)

    super_admin = db_session.scalar(select(User).where(User.username == "admin"))
    super_admin_role = db_session.scalar(select(Role).where(Role.code == "super_admin"))
    assignment = db_session.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == super_admin.id,
            UserRoleAssignment.role_id == super_admin_role.id,
        )
    )

    assert first_result.super_admin_created is True
    assert second_result.super_admin_created is False
    assert assignment is not None


def user_id_from_response(user_id: str):
    import uuid

    return uuid.UUID(user_id)
