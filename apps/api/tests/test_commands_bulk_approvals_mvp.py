from __future__ import annotations

from sqlalchemy.orm import Session

from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _submit_bulk_request(client, token: str, payload: dict[str, object]):
    return client.post(
        "/api/v1/commands/bulk-requests",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


def _list_pending_approvals(client, token: str):
    return client.get(
        "/api/v1/commands/approvals/pending",
        headers={"Authorization": f"Bearer {token}"},
    )


def _approve_command(client, token: str, command_id: str, approval_notes: str):
    return client.post(
        f"/api/v1/commands/{command_id}/approvals/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"approval_notes": approval_notes},
    )


def _reject_command(client, token: str, command_id: str, approval_notes: str):
    return client.post(
        f"/api/v1/commands/{command_id}/approvals/reject",
        headers={"Authorization": f"Bearer {token}"},
        json={"approval_notes": approval_notes},
    )


def test_bulk_command_request_submits_into_pending_approvals_and_can_be_approved(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    first_meter_id = _create_meter_record(client, token)
    second_meter_id = _create_meter_record(client, token)
    _attach_runtime_connectivity(db_session, first_meter_id)
    _attach_runtime_connectivity(db_session, second_meter_id)
    relay_template_id = _create_command_template_for_category(
        client,
        token,
        code="bulk-approvals-relay-disconnect",
        category="remote_disconnect",
    )

    bulk_response = _submit_bulk_request(
        client,
        token,
        {
            "family": "relay_control",
            "meter_ids": [first_meter_id, second_meter_id],
            "command_template_id": relay_template_id,
            "relay_operation": "disconnect",
            "notes": "Phase 2 bounded relay bulk request",
        },
    )

    assert bulk_response.status_code == 201
    bulk_payload = bulk_response.json()
    assert bulk_payload["submitted_total"] == 2
    assert bulk_payload["failed_total"] == 0
    created_command_ids = [
        item["command_id"] for item in bulk_payload["items"] if item["command_id"] is not None
    ]
    assert len(created_command_ids) == 2
    assert all(item["approval_status"] == "submitted_for_approval" for item in bulk_payload["items"])
    assert all(item["command_status"] == "pending" for item in bulk_payload["items"])

    pending_response = _list_pending_approvals(client, token)
    assert pending_response.status_code == 200
    pending_items = pending_response.json()["items"]
    pending_command_ids = {item["command_id"] for item in pending_items}
    assert created_command_ids[0] in pending_command_ids
    assert created_command_ids[1] in pending_command_ids
    approval_item = next(item for item in pending_items if item["command_id"] == created_command_ids[0])
    assert approval_item["approval_status"] == "submitted_for_approval"
    assert approval_item["command_family"] == "relay_control"

    recent_response = client.get(
        "/api/v1/commands/recent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recent_response.status_code == 200
    recent_item = next(
        item
        for item in recent_response.json()["items"]
        if item["command_id"] == created_command_ids[0]
    )
    assert recent_item["approval_status"] == "submitted_for_approval"

    approve_response = _approve_command(
        client,
        token,
        created_command_ids[0],
        "Approved for bounded relay-control MVP",
    )
    assert approve_response.status_code == 200
    approved_payload = approve_response.json()
    assert approved_payload["approval_status"] == "approved"
    assert approved_payload["current_status"] == "pending"
    assert approved_payload["approval_notes"] == "Approved for bounded relay-control MVP"

    detail_response = client.get(
        f"/api/v1/commands/{created_command_ids[0]}/detail",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["result"]
    assert detail_payload["approval_status"] == "approved"
    assert detail_payload["approval_notes"] == "Approved for bounded relay-control MVP"

    approved_recent_response = client.get(
        "/api/v1/commands/recent",
        headers={"Authorization": f"Bearer {token}"},
        params={"approval": "approved"},
    )
    assert approved_recent_response.status_code == 200
    approved_ids = {item["command_id"] for item in approved_recent_response.json()["items"]}
    assert created_command_ids[0] in approved_ids


def test_bulk_command_request_can_be_rejected_and_leaves_pending_queue(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _attach_runtime_connectivity(db_session, meter_id)
    on_demand_template_id = _create_command_template_for_category(
        client,
        token,
        code="bulk-approvals-on-demand-read",
        category="on_demand_read",
    )

    bulk_response = _submit_bulk_request(
        client,
        token,
        {
            "family": "on_demand_read",
            "meter_ids": [meter_id],
            "command_template_id": on_demand_template_id,
            "on_demand_read_operation": "read_billing_snapshot",
            "notes": "Phase 2 bounded read bulk request",
        },
    )

    assert bulk_response.status_code == 201
    command_id = bulk_response.json()["items"][0]["command_id"]

    reject_response = _reject_command(
        client,
        token,
        command_id,
        "Rejected during bounded approvals MVP review",
    )
    assert reject_response.status_code == 200
    rejected_payload = reject_response.json()
    assert rejected_payload["approval_status"] == "rejected"
    assert rejected_payload["current_status"] == "cancelled"
    assert rejected_payload["approval_notes"] == "Rejected during bounded approvals MVP review"

    pending_response = _list_pending_approvals(client, token)
    assert pending_response.status_code == 200
    pending_command_ids = {item["command_id"] for item in pending_response.json()["items"]}
    assert command_id not in pending_command_ids

    rejected_recent_response = client.get(
        "/api/v1/commands/recent",
        headers={"Authorization": f"Bearer {token}"},
        params={"approval": "rejected"},
    )
    assert rejected_recent_response.status_code == 200
    rejected_ids = {item["command_id"] for item in rejected_recent_response.json()["items"]}
    assert command_id in rejected_ids
