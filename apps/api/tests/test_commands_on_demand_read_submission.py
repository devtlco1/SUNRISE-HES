from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.models import CommandTemplate, MeterCommand
from app.modules.connectivity.enums import (
    AssociationAuthenticationMode,
    ConnectivityTransportType,
    EndpointAssignmentStatus,
)
from app.modules.connectivity.models import MeterEndpointAssignment, ProtocolAssociationProfile
from app.modules.meters.models import Meter
from app.modules.readings.enums import SnapshotType
from app.runtime.adapters.dlms_cosem import GuruxDlmsAdapterBridge
from app.runtime.contracts import (
    MeterRuntimeTarget,
    RuntimeExecutionContext,
    RuntimeExecutionSessionLineage,
    RuntimeOnDemandReadAdapterRequest,
    RuntimeOnDemandReadOperation,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from tests.test_commands_foundation import _login_as_super_admin
from tests.test_commands_profile_capture_submission import _create_command_template_for_category
from tests.test_protocol_runtime_foundation import _attach_runtime_connectivity, _create_meter_record


def _submit_on_demand_read_command(
    client,
    token: str,
    meter_id: str,
    *,
    command_template_id: str,
    endpoint_assignment_id: str,
    protocol_association_profile_id: str,
    on_demand_read_operation: str = "read_billing_snapshot",
    idempotency_key: str | None = None,
    include_operation: bool = True,
):
    payload = {
        "command_template_id": command_template_id,
        "endpoint_assignment_id": endpoint_assignment_id,
        "protocol_association_profile_id": protocol_association_profile_id,
        "priority": "high",
        "idempotency_key": idempotency_key,
        "notes": "On-demand billing snapshot request",
    }
    if include_operation:
        payload["on_demand_read_operation"] = on_demand_read_operation
    return client.post(
        f"/api/v1/meters/{meter_id}/commands/on-demand-read",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


def test_submit_on_demand_read_command_with_valid_prerequisites(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-valid",
        category="on_demand_read",
    )

    response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-valid-1",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["command_template_code"] == "on-demand-read-valid"
    assert payload["endpoint_assignment_id"] == endpoint_assignment_id
    assert payload["protocol_association_profile_id"] == protocol_profile_id
    assert payload["normalized_payload"]["on_demand_read_operation"] == "read_billing_snapshot"
    assert payload["normalized_payload"]["on_demand_read"]["snapshot_type"] == "billing"
    assert payload["normalized_payload"]["on_demand_read"]["command_category"] == "on_demand_read"


def test_submit_on_demand_read_command_refuses_non_compatible_template(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-wrong-template",
        category="profile_capture",
    )

    response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-wrong-template-1",
    )

    assert response.status_code == 409
    assert "not compatible" in response.json()["detail"].lower()


def test_submit_on_demand_read_command_refuses_invalid_endpoint_assignment(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-invalid-endpoint",
        category="on_demand_read",
    )

    response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=str(uuid.uuid4()),
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-invalid-endpoint-1",
    )

    assert response.status_code == 400
    assert "endpoint assignment is invalid" in response.json()["detail"].lower()


def test_submit_on_demand_read_command_refuses_inactive_endpoint_assignment(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-inactive-endpoint",
        category="on_demand_read",
    )
    assignment = db_session.get(MeterEndpointAssignment, UUID(endpoint_assignment_id))
    assert assignment is not None
    assignment.assignment_status = EndpointAssignmentStatus.INACTIVE
    db_session.add(assignment)
    db_session.commit()

    response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-inactive-endpoint-1",
    )

    assert response.status_code == 409
    assert "endpoint assignment is not active" in response.json()["detail"].lower()


def test_submit_on_demand_read_command_refuses_missing_protocol_profile(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, _ = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-missing-profile",
        category="on_demand_read",
    )

    response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=str(uuid.uuid4()),
        idempotency_key="on-demand-read-missing-profile-1",
    )

    assert response.status_code == 404
    assert "protocol association profile not found" in response.json()["detail"].lower()


def test_submit_on_demand_read_command_refuses_invalid_or_missing_operation(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-invalid-operation",
        category="on_demand_read",
    )

    invalid_response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        on_demand_read_operation="read_instantaneous_snapshot",
        idempotency_key="on-demand-read-invalid-operation-1",
    )
    missing_response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        include_operation=False,
        idempotency_key="on-demand-read-invalid-operation-2",
    )

    assert invalid_response.status_code == 422
    assert missing_response.status_code == 422


def test_on_demand_read_submission_persists_normalized_payload_for_runtime_slice(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-runtime-compatible",
        category="on_demand_read",
    )

    response = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-runtime-compatible-1",
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

    result = GuruxDlmsAdapterBridge().execute_on_demand_read(
        RuntimeOnDemandReadAdapterRequest(
            adapter_key="gurux-dlms-bridge",
            protocol_family=profile.protocol_family,
            operation=RuntimeOnDemandReadOperation.READ_BILLING_SNAPSHOT,
            command_category=template.category,
            execution_context=RuntimeExecutionContext(
                command_id=command.id,
                job_run_id=uuid.uuid4(),
                command_attempt_id=uuid.uuid4(),
                correlation_id=command.correlation_id,
                worker_identifier="worker-runtime-1",
                request_id="request-on-demand-read-command",
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
            protocol_profile_code=profile.code,
            iec62056_21_enabled=profile.iec62056_21_enabled,
            iec_device_address=profile.iec_device_address,
            iec_baud_rate=profile.iec_baud_rate,
            client_address=profile.client_address,
            server_address=profile.server_address,
            server_address_size=int((profile.profile_settings or {}).get("server_address_size", 1)),
            protocol_settings=profile.profile_settings,
            protocol_defaults=meter.meter_profile.protocol_defaults if meter.meter_profile is not None else None,
            request_payload=command.request_payload,
            normalized_payload=command.normalized_payload,
            dispatch_envelope_record_id="dispatch-envelope-command-on-demand-read",
            trace_references={
                "session_identifier": "session-command-on-demand-read",
                "delivery_contract_record_id": "delivery-contract-on-demand-read",
                "envelope_record_id": "envelope-on-demand-read",
                "publication_contract_record_id": "publication-contract-on-demand-read",
                "attestation_record_id": "attestation-on-demand-read",
                "settlement_record_id": "settlement-on-demand-read",
                "reconciliation_record_id": "reconciliation-on-demand-read",
                "interpretation_record_id": "interpretation-on-demand-read",
                "observation_record_id": "observation-on-demand-read",
                "invocation_result_record_id": "invocation-result-on-demand-read",
                "dispatch_request_record_id": "dispatch-request-on-demand-read",
                "selection_record_id": "selection-on-demand-read",
                "intent_record_id": "intent-on-demand-read",
                "closure_record_id": "closure-on-demand-read",
                "materialization_record_id": "materialization-on-demand-read",
                "post_processing_record_id": "post-processing-on-demand-read",
                "disposition_record_id": "disposition-on-demand-read",
                "outcome_record_id": "outcome-on-demand-read",
            },
            lineage=RuntimeExecutionSessionLineage(
                dispatch_request_identity="dispatch-command-on-demand-read",
                queue_message_id="queue-command-on-demand-read",
                claim_token="claim-command-on-demand-read",
                intended_worker_path="runtime-on-demand-read",
            ),
        )
    )

    assert result.on_demand_read_operation == RuntimeOnDemandReadOperation.READ_BILLING_SNAPSHOT
    assert result.command_category == template.category
    assert result.snapshot_type == SnapshotType.BILLING
    assert result.register_snapshot is not None


def test_submit_on_demand_read_command_is_idempotent_for_same_key(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_for_category(
        client,
        token,
        code="on-demand-read-idempotent",
        category="on_demand_read",
    )

    first = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-idempotent-1",
    )
    second = _submit_on_demand_read_command(
        client,
        token,
        meter_id,
        command_template_id=template_id,
        endpoint_assignment_id=endpoint_assignment_id,
        protocol_association_profile_id=protocol_profile_id,
        idempotency_key="on-demand-read-idempotent-1",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["normalized_payload"] == second.json()["normalized_payload"]
