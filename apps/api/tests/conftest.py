from collections.abc import Generator
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _running_inside_container() -> bool:
    return Path("/.dockerenv").exists()


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


def _normalize_test_service_url(url: str) -> str:
    if _running_inside_container():
        return url

    resolved = _replace_service_hostname(
        url,
        service_host="postgres",
        replacement_host="127.0.0.1",
    )
    return _replace_service_hostname(
        resolved,
        service_host="redis",
        replacement_host="127.0.0.1",
    )


def _with_test_database_name(url: str) -> str:
    parsed = make_url(url)
    database_name = parsed.database or "sunrise_hes"
    if database_name.endswith("_test"):
        return parsed.render_as_string(hide_password=False)
    return parsed.set(database=f"{database_name}_test").render_as_string(hide_password=False)


def _resolve_test_database_url() -> str:
    explicit_test_database_url = os.getenv("TEST_DATABASE_URL")
    if explicit_test_database_url:
        return _normalize_test_service_url(explicit_test_database_url)
    return _with_test_database_name(_normalize_test_service_url(settings.database_url))


def _ensure_database_exists(database_url: str) -> None:
    parsed = make_url(database_url)
    database_name = parsed.database
    if not database_name:
        raise RuntimeError("Test database URL must include a database name.")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
        raise RuntimeError("Test database name contains unsupported characters.")

    admin_database_url = parsed.set(database="postgres")
    admin_engine = create_engine(
        admin_database_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    try:
        with admin_engine.connect() as connection:
            template_postgis_exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'template_postgis'")
            ).scalar()
            database_exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            ).scalar()
            if database_exists is None:
                if template_postgis_exists is not None:
                    connection.execute(
                        text(f'CREATE DATABASE "{database_name}" TEMPLATE template_postgis')
                    )
                else:
                    connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin_engine.dispose()

    test_engine = create_engine(database_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with test_engine.connect() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    finally:
        test_engine.dispose()


TEST_DATABASE_URL = _resolve_test_database_url()
TEST_REDIS_URL = _normalize_test_service_url(settings.redis_url)
_ensure_database_exists(TEST_DATABASE_URL)
settings.database_url = TEST_DATABASE_URL
settings.redis_url = TEST_REDIS_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL

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
    settings.database_url = TEST_DATABASE_URL
    settings.redis_url = TEST_REDIS_URL
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
