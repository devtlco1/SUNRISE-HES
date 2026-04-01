from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db_session
from app.main import app
from app.modules.users.enums import UserStatus
from app.modules.users.models import Role, User, UserRoleAssignment


def _startup_client(db_session: Session) -> TestClient:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def test_startup_bootstraps_super_admin_and_allows_login(db_session: Session) -> None:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"

    with _startup_client(db_session) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
            json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    db_session.expire_all()
    super_admin = db_session.scalar(select(User).where(User.username == "admin"))
    assert super_admin is not None
    assert super_admin.email == "admin@example.com"
    assert super_admin.is_superuser is True
    assert super_admin.status == UserStatus.ACTIVE


def test_startup_bootstrap_remains_idempotent(db_session: Session) -> None:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"

    with _startup_client(db_session):
        pass
    app.dependency_overrides.clear()
    with _startup_client(db_session):
        pass
    app.dependency_overrides.clear()

    db_session.expire_all()
    super_admin_role = db_session.scalar(select(Role).where(Role.code == "super_admin"))
    assert super_admin_role is not None

    super_admin_count = db_session.scalar(
        select(func.count()).select_from(User).where(User.username == "admin")
    )
    super_admin_assignment_count = db_session.scalar(
        select(func.count())
        .select_from(UserRoleAssignment)
        .join(User, User.id == UserRoleAssignment.user_id)
        .where(
            User.username == "admin",
            UserRoleAssignment.role_id == super_admin_role.id,
            UserRoleAssignment.scope_type == "platform",
            UserRoleAssignment.scope_identifier == "global",
        )
    )

    assert super_admin_count == 1
    assert super_admin_assignment_count == 1


def test_startup_bootstrap_repairs_existing_super_admin_credentials(db_session: Session) -> None:
    db_session.add(
        User(
            username="admin",
            email="admin@example.com",
            full_name="Platform Super Admin",
            password_hash="invalid-password-hash",
            status=UserStatus.ACTIVE,
            is_superuser=True,
        )
    )
    db_session.commit()

    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"

    with _startup_client(db_session) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
            json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
