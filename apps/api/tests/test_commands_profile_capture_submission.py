from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandTemplate, MeterCommand
from app.modules.connectivity.enums import AssociationAuthenticationMode, ConnectivityTransportType, ProtocolFamily
from app.modules.connectivity.models import MeterEndpointAssignment, ProtocolAssociationProfile
from app.modules.readings.models import LoadProfileChannel
from app.runtime.adapters.dlms_cosem import (
    _map_profile_read_operation_to_gurux_definition,
    _validate_gurux_capture_load_profile_target,
)
from app.runtime.contracts import (
    MeterRuntimeTarget,
    RuntimeExecutionContext,
    RuntimeExecutionSessionLineage,
    RuntimeProfileReadAdapterRequest,
    RuntimeProfileReadOperation,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record
from tests.test_worker_runtime_executor_foundation import _create_load_profile_channel


def _create_command_template_for_category(client, token: str, *, code: str, category: str) -> str:
    response = client.post(
        "/api/v1/command-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "name": code.replace("-", " ").title(),
            "category": category,
            "target_scope": "meter",
            "timeout_seconds": 120,
            "max_retries": 0,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _submit_profile_capture_command(
    client,
    token: str,
    meter_id: str,
    *,
    command_template_id: str,
    endpoint_assignment_id: str,
    protocol_association_profile_id: str,
    channel_ids: list[str],
    idempotency_key: str | None = None,
):
    interval_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    interval_end = interval_start + timedelta(minutes=15)
    return client.post(
        f"/api/v1/meters/{meter_id}/commands/profile-capture",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": command_template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_association_profile_id,
            "channel_ids": channel_ids,
            "interval_start": interval_start.isoformat(),
            "interval_end": interval_end.isoformat(),
            "priority": "high",
            "idempotency_key": idempotency_key,
            "notes": "Profile capture request",
        },
    )


def test_submit_capture_load_profile_command_with_valid_prerequisites(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="capture-load-profile-valid",
        category="profile_capture",
    )

    response = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="capture-load-profile-valid-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["command_template_code"] == "capture-load-profile-valid"
    assert payload["endpoint_assignment_id"] == endpoint_assignment_id
    assert payload["protocol_association_profile_id"] == protocol_profile_id
    assert payload["normalized_payload"]["profile_read_operation"] == "capture_load_profile"
    assert payload["normalized_payload"]["capture_load_profile"]["channel_count"] == 1
    assert payload["normalized_payload"]["capture_load_profile"]["channel_ids"] == [channel_id]


def test_submit_capture_load_profile_command_refuses_non_profile_capture_template(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="capture-load-profile-wrong-template",
        category="on_demand_read",
    )

    response = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
    )

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_submit_capture_load_profile_command_refuses_invalid_endpoint_assignment(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="capture-load-profile-invalid-endpoint",
        category="profile_capture",
    )

    response = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=str(uuid.uuid4()),
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
    )

    assert response.status_code == 400
    assert "endpoint assignment is invalid" in response.json()["detail"].lower()


def test_submit_capture_load_profile_command_refuses_invalid_protocol_profile(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, _ = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="capture-load-profile-invalid-profile",
        category="profile_capture",
    )

    response = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=str(uuid.uuid4()),
        channel_ids=[channel_id],
    )

    assert response.status_code == 404
    assert "protocol association profile not found" in response.json()["detail"].lower()


def test_submit_capture_load_profile_command_is_idempotent_for_same_key(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="capture-load-profile-idempotent",
        category="profile_capture",
    )

    first = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="capture-load-profile-idempotent-1",
    )
    second = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="capture-load-profile-idempotent-1",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["normalized_payload"] == second.json()["normalized_payload"]


def test_capture_load_profile_submission_normalized_payload_is_consumable_by_runtime_slice(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    channel_id = _create_load_profile_channel(client, token, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="capture-load-profile-runtime-compatible",
        category="profile_capture",
    )

    response = _submit_profile_capture_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        channel_ids=[channel_id],
        idempotency_key="capture-load-profile-runtime-compatible-1",
    )
    assert response.status_code == 200
    command_id = UUID(response.json()["id"])

    command = db_session.scalar(select(MeterCommand).where(MeterCommand.id == command_id))
    assignment = db_session.get(MeterEndpointAssignment, UUID(endpoint_assignment_id))
    profile = db_session.get(ProtocolAssociationProfile, UUID(protocol_profile_id))
    channel = db_session.get(LoadProfileChannel, UUID(channel_id))
    template = db_session.get(CommandTemplate, UUID(template_id))
    assert command is not None
    assert assignment is not None
    assert profile is not None
    assert channel is not None
    assert template is not None

    request = RuntimeProfileReadAdapterRequest(
        adapter_key="gurux-dlms-bridge",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        operation=RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE,
        command_category=template.category,
        execution_context=RuntimeExecutionContext(
            command_id=command.id,
            job_run_id=uuid.uuid4(),
            command_attempt_id=uuid.uuid4(),
            correlation_id=command.correlation_id,
            worker_identifier="worker-runtime-1",
            request_id="request-profile-capture-command",
            triggered_at=datetime.now(UTC),
        ),
        target=MeterRuntimeTarget(
            meter_id=UUID(meter_id),
            serial_number="COMMAND-CAPTURE-SN",
            utility_meter_number="COMMAND-CAPTURE-UMN",
            manufacturer_code="runtime-vendor",
            meter_model_code="runtime-model",
            meter_model_name="Runtime Model",
            endpoint_assignment_id=assignment.id,
            endpoint_id=assignment.endpoint_id,
            endpoint_code=assignment.endpoint.code,
            protocol_association_profile_id=profile.id,
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=ConnectivityTransportType.TCP_IP,
            host=assignment.endpoint.host,
            port=assignment.endpoint.port,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=AssociationAuthenticationMode(profile.authentication_mode.value),
            password_secret_ref=profile.password_secret_ref,
            security_suite=profile.security_suite,
            system_title=profile.system_title,
            auth_key_ref=profile.auth_key_ref,
            block_cipher_key_ref=profile.block_cipher_key_ref,
            dedicated_key_ref=profile.dedicated_key_ref,
        ),
        request_payload=command.request_payload,
        normalized_payload=command.normalized_payload,
        dispatch_envelope_record_id="dispatch-envelope-command-profile-capture",
        trace_references={"session_identifier": "session-command-profile-capture"},
        lineage=RuntimeExecutionSessionLineage(
            dispatch_request_identity="dispatch-command-profile-capture",
            queue_message_id="queue-command-profile-capture",
            claim_token="claim-command-profile-capture",
            intended_worker_path="runtime-profile-read",
        ),
    )

    validated_target = _validate_gurux_capture_load_profile_target(
        request,
        _map_profile_read_operation_to_gurux_definition(
            RuntimeProfileReadOperation.CAPTURE_LOAD_PROFILE
        ),
    )

    assert validated_target.requested_channel_ids == [str(channel.id)]
    assert validated_target.requested_interval_count == 1
