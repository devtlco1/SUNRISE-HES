from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandTemplate, MeterCommand
from app.modules.connectivity.enums import AssociationAuthenticationMode, ConnectivityTransportType
from app.modules.connectivity.models import MeterEndpointAssignment, ProtocolAssociationProfile
from app.modules.meters.models import Meter
from app.runtime.adapters.dlms_cosem import GuruxDlmsAdapterBridge
from app.runtime.contracts import (
    MeterRuntimeTarget,
    RuntimeExecutionContext,
    RuntimeExecutionSessionLineage,
    RuntimeRelayControlAdapterRequest,
    RuntimeRelayControlOperation,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _submit_relay_control_command(
    client,
    token: str,
    meter_id: str,
    *,
    command_template_id: str,
    relay_operation: str,
    endpoint_assignment_id: str,
    protocol_association_profile_id: str,
    relay_target_interface_class: str = "disconnect_control",
    relay_target_obis_code: str = "0.0.96.3.10.255",
    idempotency_key: str | None = None,
):
    return client.post(
        f"/api/v1/meters/{meter_id}/commands/relay-control",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": command_template_id,
            "relay_operation": relay_operation,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_association_profile_id,
            "relay_target_interface_class": relay_target_interface_class,
            "relay_target_obis_code": relay_target_obis_code,
            "priority": "high",
            "idempotency_key": idempotency_key,
            "notes": "Relay control request",
        },
    )


def test_submit_relay_control_command_with_valid_disconnect_prerequisites(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-disconnect-valid",
        category="remote_disconnect",
    )

    response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-disconnect-valid-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["command_template_code"] == "relay-control-disconnect-valid"
    assert payload["endpoint_assignment_id"] == endpoint_assignment_id
    assert payload["protocol_association_profile_id"] == protocol_profile_id
    assert payload["normalized_payload"]["relay_control_operation"] == "disconnect"
    assert payload["normalized_payload"]["relay_control"]["target_object"]["interface_class"] == (
        "disconnect_control"
    )
    assert payload["normalized_payload"]["relay_control"]["target_object"]["obis_code"] == (
        "0.0.96.3.10.255"
    )
    assert payload["normalized_payload"]["relay_control"]["target_object"]["method_name"] == (
        "remote_disconnect"
    )


def test_submit_relay_control_command_refuses_non_relay_compatible_template(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-wrong-template",
        category="profile_capture",
    )

    response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-wrong-template-1",
    )

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_submit_relay_control_command_refuses_invalid_endpoint_assignment(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-invalid-endpoint",
        category="remote_disconnect",
    )

    response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=str(uuid.uuid4()),
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-invalid-endpoint-1",
    )

    assert response.status_code == 400
    assert "endpoint assignment is invalid" in response.json()["detail"].lower()


def test_submit_relay_control_command_refuses_inactive_protocol_profile(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-inactive-profile",
        category="remote_disconnect",
    )
    profile = db_session.get(ProtocolAssociationProfile, UUID(protocol_profile_id))
    assert profile is not None
    profile.is_active = False
    db_session.add(profile)
    db_session.commit()

    response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-inactive-profile-1",
    )

    assert response.status_code == 409
    assert "protocol association profile is not active" in response.json()["detail"].lower()


def test_submit_relay_control_command_refuses_invalid_relay_target_assumptions(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-invalid-target",
        category="remote_disconnect",
    )

    response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        relay_target_obis_code="1.0.99.1.0.255",
        idempotency_key="relay-control-invalid-target-1",
    )

    assert response.status_code == 409
    assert "target assumptions" in response.json()["detail"].lower()


def test_submit_relay_control_command_is_idempotent_for_same_key(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-idempotent",
        category="remote_reconnect",
    )

    first = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="reconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-idempotent-1",
    )
    second = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="reconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-idempotent-1",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["normalized_payload"] == second.json()["normalized_payload"]


def test_relay_control_submission_normalized_payload_is_consumable_by_runtime_slice(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="relay-control-runtime-compatible",
        category="remote_disconnect",
    )

    response = _submit_relay_control_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        relay_operation="disconnect",
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="relay-control-runtime-compatible-1",
    )
    assert response.status_code == 200
    command_id = UUID(response.json()["id"])

    command = db_session.scalar(select(MeterCommand).where(MeterCommand.id == command_id))
    meter = db_session.get(Meter, UUID(meter_id))
    assignment = db_session.get(MeterEndpointAssignment, UUID(endpoint_assignment_id))
    profile = db_session.get(ProtocolAssociationProfile, UUID(protocol_profile_id))
    template = db_session.get(CommandTemplate, UUID(template_id))
    assert command is not None
    assert meter is not None
    assert assignment is not None
    assert profile is not None
    assert template is not None

    result = GuruxDlmsAdapterBridge().execute_relay_control(
        RuntimeRelayControlAdapterRequest(
            adapter_key="gurux-dlms-bridge",
            protocol_family=profile.protocol_family,
            operation=RuntimeRelayControlOperation.DISCONNECT,
            command_category=template.category,
            execution_context=RuntimeExecutionContext(
                command_id=command.id,
                job_run_id=uuid.uuid4(),
                command_attempt_id=uuid.uuid4(),
                correlation_id=command.correlation_id,
                worker_identifier="worker-runtime-1",
                request_id="request-relay-control-command",
                triggered_at=datetime.now(UTC),
            ),
            target=MeterRuntimeTarget(
                meter_id=meter.id,
                serial_number=meter.serial_number,
                utility_meter_number=meter.utility_meter_number,
                meter_profile_id=meter.meter_profile_id,
                manufacturer_code=meter.manufacturer.code,
                meter_model_code=meter.meter_model.model_code,
                meter_model_name=meter.meter_model.display_name,
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
            dispatch_envelope_record_id="dispatch-envelope-command-relay-control",
            trace_references={
                "session_identifier": "session-command-relay-control",
                "delivery_contract_record_id": "delivery-contract-relay-control",
                "envelope_record_id": "envelope-relay-control",
                "publication_contract_record_id": "publication-contract-relay-control",
                "attestation_record_id": "attestation-relay-control",
                "settlement_record_id": "settlement-relay-control",
                "reconciliation_record_id": "reconciliation-relay-control",
                "interpretation_record_id": "interpretation-relay-control",
                "observation_record_id": "observation-relay-control",
                "invocation_result_record_id": "invocation-result-relay-control",
                "dispatch_request_record_id": "dispatch-request-relay-control",
                "selection_record_id": "selection-relay-control",
                "intent_record_id": "intent-relay-control",
                "closure_record_id": "closure-relay-control",
                "materialization_record_id": "materialization-relay-control",
                "post_processing_record_id": "post-processing-relay-control",
                "disposition_record_id": "disposition-relay-control",
                "outcome_record_id": "outcome-relay-control",
            },
            lineage=RuntimeExecutionSessionLineage(
                dispatch_request_identity="dispatch-command-relay-control",
                queue_message_id="queue-command-relay-control",
                claim_token="claim-command-relay-control",
                intended_worker_path="runtime-relay-control",
            ),
        )
    )

    assert result.relay_operation == RuntimeRelayControlOperation.DISCONNECT
    assert result.command_category == template.category
    assert result.adapter_result_summary["gurux_operation"]["method_name"] == "remote_disconnect"
