from app.core.config import settings
from app.modules.auth.bootstrap import bootstrap_access_control


def test_auth_login_preflight_allows_localhost_frontend_origin(client) -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_auth_login_preflight_allows_deployed_frontend_origin(client) -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://187.124.187.156:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://187.124.187.156:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_auth_login_response_includes_cors_headers_for_allowed_origin(client, db_session) -> None:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"
    bootstrap_access_control(db_session)

    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:3000"},
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_auth_login_response_includes_cors_headers_for_deployed_origin(
    client, db_session
) -> None:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"
    bootstrap_access_control(db_session)

    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://187.124.187.156:3000"},
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://187.124.187.156:3000"


def test_auth_invalid_login_response_includes_cors_headers_for_allowed_origin(client) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:3000"},
        json={"username_or_email": "admin", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.json()["detail"] == "Invalid username/email or password."


def test_auth_login_preflight_rejects_disallowed_origin(client) -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:4000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_forgot_password_preflight_allows_localhost_frontend_origin(client) -> None:
    response = client.options(
        "/api/v1/auth/forgot-password",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_forgot_password_preflight_allows_deployed_frontend_origin(client) -> None:
    response = client.options(
        "/api/v1/auth/forgot-password",
        headers={
            "Origin": "http://187.124.187.156:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://187.124.187.156:3000"


def test_forgot_password_response_includes_cors_headers_for_allowed_origin(client) -> None:
    response = client.post(
        "/api/v1/auth/forgot-password",
        headers={"Origin": "http://localhost:3000"},
        json={"username_or_email": "admin@example.com"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
