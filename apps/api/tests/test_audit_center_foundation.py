from __future__ import annotations

import uuid

from app.modules.audit.service import record_audit_event
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.users.schemas import RoleCreate, UserCreate, UserRoleAssignmentRequest
from app.modules.users.service import assign_role_to_user, create_role, create_user


def test_list_audit_logs_returns_real_audit_rows_with_filters(client, db_session) -> None:
    bootstrap_access_control(db_session)

    audit_viewer_role = create_role(
        db_session,
        RoleCreate(
            code="audit_viewer",
            name="Audit Viewer",
            permission_codes=["auth.me", "audit.read"],
        ),
    )
    viewer_user = create_user(
        db_session,
        UserCreate(
            username="audit.viewer",
            email="audit.viewer@example.com",
            full_name="Audit Viewer",
            password="SecurePassword123!",
        ),
    )
    assign_role_to_user(
        db_session,
        user_id=viewer_user.id,
        payload=UserRoleAssignmentRequest(role_id=audit_viewer_role.id),
        assigned_by_user_id=None,
    )

    operator_user = create_user(
        db_session,
        UserCreate(
            username="ops.trace",
            email="ops.trace@example.com",
            full_name="Ops Trace",
            password="SecurePassword123!",
        ),
    )
    record_audit_event(
        db_session,
        action="commands.approvals.approve",
        resource_type="commands",
        actor_user_id=operator_user.id,
        outcome="failure",
        description="Command approval failed.",
        details={"reason": "validation_error"},
    )
    record_audit_event(
        db_session,
        action="auth.login.success",
        resource_type="auth",
        actor_user_id=viewer_user.id,
        outcome="success",
        description="Authentication succeeded.",
        details={"username": viewer_user.username},
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "audit.viewer", "password": "SecurePassword123!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/audit-logs?actor=Ops%20Trace&entity_type=commands&outcome=failure",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["actor_username"] == "ops.trace"
    assert payload["items"][0]["actor_full_name"] == "Ops Trace"
    assert payload["items"][0]["action"] == "commands.approvals.approve"
    assert payload["items"][0]["entity_type"] == "commands"
    assert payload["items"][0]["description"] == "Command approval failed."
    assert payload["items"][0]["payload"]["outcome"] == "failure"
    assert payload["items"][0]["payload"]["details"]["reason"] == "validation_error"


def test_list_audit_logs_requires_audit_read_permission(client, db_session) -> None:
    bootstrap_access_control(db_session)

    auth_only_role = create_role(
        db_session,
        RoleCreate(
            code="auth_only",
            name="Auth Only",
            permission_codes=["auth.me"],
        ),
    )
    limited_user = create_user(
        db_session,
        UserCreate(
            username="limited.audit",
            email="limited.audit@example.com",
            full_name="Limited Audit",
            password="SecurePassword123!",
        ),
    )
    assign_role_to_user(
        db_session,
        user_id=limited_user.id,
        payload=UserRoleAssignmentRequest(role_id=auth_only_role.id),
        assigned_by_user_id=None,
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "limited.audit", "password": "SecurePassword123!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "audit.read" in response.json()["detail"]


def test_list_audit_logs_supports_entity_id_filter(client, db_session) -> None:
    bootstrap_access_control(db_session)

    audit_viewer_role = create_role(
        db_session,
        RoleCreate(
            code="meter_audit_viewer",
            name="Meter Audit Viewer",
            permission_codes=["auth.me", "audit.read"],
        ),
    )
    viewer_user = create_user(
        db_session,
        UserCreate(
            username="meter.audit.viewer",
            email="meter.audit.viewer@example.com",
            full_name="Meter Audit Viewer",
            password="SecurePassword123!",
        ),
    )
    assign_role_to_user(
        db_session,
        user_id=viewer_user.id,
        payload=UserRoleAssignmentRequest(role_id=audit_viewer_role.id),
        assigned_by_user_id=None,
    )

    first_meter_id = uuid.uuid4()
    second_meter_id = uuid.uuid4()

    record_audit_event(
        db_session,
        action="meters.update",
        resource_type="meters",
        resource_id=first_meter_id,
        actor_user_id=viewer_user.id,
        outcome="success",
        description="Primary meter updated.",
        details={"field": "status"},
    )
    record_audit_event(
        db_session,
        action="meters.update",
        resource_type="meters",
        resource_id=second_meter_id,
        actor_user_id=viewer_user.id,
        outcome="success",
        description="Secondary meter updated.",
        details={"field": "status"},
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "meter.audit.viewer", "password": "SecurePassword123!"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        f"/api/v1/audit-logs?entity_type=meters&entity_id={first_meter_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["entity_type"] == "meters"
    assert payload["items"][0]["entity_id"] == str(first_meter_id)
    assert payload["items"][0]["description"] == "Primary meter updated."
