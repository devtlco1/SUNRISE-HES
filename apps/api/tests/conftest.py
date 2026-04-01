from collections.abc import Generator
from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.db import get_db_session
from app.db.base import Base
from app.db import models as db_models  # noqa: F401
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.meters.models import (
    CommunicationProfile,
    Meter,
    MeterFirmwareVersion,
    MeterManufacturer,
    MeterModel,
    MeterProfile,
    MeterStatusHistory,
)
from app.modules.users.models import Permission, Role, RolePermission, User, UserRoleAssignment


def _replace_service_hostname(url: str, *, service_host: str, replacement_host: str) -> str:
    parts = urlsplit(url)
    if parts.hostname != service_host:
        return url

    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo = f"{userinfo}:{parts.password}"
        userinfo = f"{userinfo}@"

    port = f":{parts.port}" if parts.port is not None else ""
    netloc = f"{userinfo}{replacement_host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@pytest.fixture()
def db_session(local_test_service_settings: None) -> Generator[Session, None, None]:
    engine = create_engine(settings.database_url)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    Base.metadata.create_all(bind=engine)

    truncate_sql = text(
        "TRUNCATE TABLE "
        "audit_logs, command_execution_attempts, command_templates, commands, "
        "job_runs, job_definition_target_assignments, jobs, "
        "meter_readings, meter_register_snapshots, load_profile_intervals, load_profile_channels, meter_reading_batches, "
        "meter_events, connectivity_session_history, meter_endpoint_assignments, connectivity_credentials, "
        "protocol_association_profiles, communication_endpoints, meter_status_history, meters, meter_profiles, communication_profiles, "
        "meter_firmware_versions, meter_models, meter_manufacturers, "
        "user_role_assignments, role_permissions, permissions, roles, users "
        "RESTART IDENTITY CASCADE"
    )
    with engine.begin() as connection:
        connection.execute(truncate_sql)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as connection:
            connection.execute(truncate_sql)
        engine.dispose()


@pytest.fixture(autouse=True)
def local_test_service_settings() -> Generator[None, None, None]:
    original_values = {
        "database_url": settings.database_url,
        "redis_url": settings.redis_url,
    }
    settings.database_url = _replace_service_hostname(
        settings.database_url,
        service_host="postgres",
        replacement_host="127.0.0.1",
    )
    settings.redis_url = _replace_service_hostname(
        settings.redis_url,
        service_host="redis",
        replacement_host="127.0.0.1",
    )
    try:
        yield
    finally:
        for key, value in original_values.items():
            setattr(settings, key, value)


@pytest.fixture(autouse=True)
def auth_settings(local_test_service_settings: None) -> Generator[None, None, None]:
    original_values = {
        "jwt_secret_key": settings.jwt_secret_key,
        "jwt_algorithm": settings.jwt_algorithm,
        "jwt_access_token_expire_minutes": settings.jwt_access_token_expire_minutes,
        "jwt_issuer": settings.jwt_issuer,
        "cors_allowed_origins": settings.cors_allowed_origins,
        "internal_api_token": settings.internal_api_token,
        "bootstrap_super_admin_username": settings.bootstrap_super_admin_username,
        "bootstrap_super_admin_email": settings.bootstrap_super_admin_email,
        "bootstrap_super_admin_full_name": settings.bootstrap_super_admin_full_name,
        "bootstrap_super_admin_password": settings.bootstrap_super_admin_password,
    }
    settings.jwt_secret_key = "test-secret-key-with-at-least-32-chars"
    settings.jwt_algorithm = "HS256"
    settings.jwt_access_token_expire_minutes = 30
    settings.jwt_issuer = "sunrise-hes-platform-test"
    settings.cors_allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    settings.internal_api_token = "test-internal-token"
    settings.bootstrap_super_admin_username = None
    settings.bootstrap_super_admin_email = None
    settings.bootstrap_super_admin_full_name = "Platform Super Admin"
    settings.bootstrap_super_admin_password = None
    try:
        yield
    finally:
        for key, value in original_values.items():
            setattr(settings, key, value)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
