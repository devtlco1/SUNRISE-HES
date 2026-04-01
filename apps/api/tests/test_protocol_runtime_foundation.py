from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.commands.enums import CommandCategory
from app.modules.connectivity.enums import (
    AssociationAuthenticationMode,
    CommunicationEndpointType,
    ConnectivitySessionPurpose,
    ConnectivitySessionStatus,
    ConnectivityTransportType,
    EndpointAssignmentStatus,
    ProtocolFamily,
)
from app.modules.connectivity.models import (
    CommunicationEndpoint,
    MeterEndpointAssignment,
    ProtocolAssociationProfile,
)
from app.modules.events.enums import EventSeverity, EventState
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.meters.enums import AuthenticationMode, IPMode, TransportType
from app.modules.meters.models import CommunicationProfile, Meter
from app.modules.readings.enums import ReadingBatchStatus, ReadingSourceType, ReadingType, SnapshotType
from app.runtime.normalization import (
    to_command_result_summary,
    to_meter_events_ingest_request,
    to_reading_batch_ingest_request,
)
from app.runtime.planning import map_command_category_to_runtime_intent
from app.runtime.contracts import (
    RuntimeCommandOutcome,
    RuntimeCommandResult,
    RuntimeEventPayload,
    RuntimeLoadProfileIntervalPayload,
    RuntimeReadingBatchPayload,
    RuntimeReadingPayload,
    RuntimeRegisterSnapshotPayload,
    RuntimeSessionResult,
)


def _login_as_super_admin(client, db_session: Session) -> str:
    settings.bootstrap_super_admin_username = "admin"
    settings.bootstrap_super_admin_email = "admin@example.com"
    settings.bootstrap_super_admin_password = "ChangeThisPassword123!"
    bootstrap_access_control(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "ChangeThisPassword123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_build_runtime_plan_from_valid_meter_command(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    template_id = _create_command_template_record(client, token, "runtime-on-demand-read")

    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_profile_id,
            "idempotency_key": f"runtime-cmd-{_suffix()}",
            "request_payload": {"obis": ["1.0.1.8.0.255"], "capture_mode": "current"},
        },
    )
    assert command_response.status_code == 201
    command_id = command_response.json()["id"]

    response = client.post(
        f"/api/v1/internal/commands/{command_id}/build-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["adapter_key"] == "gurux-dlms-bridge"
    assert payload["protocol_family"] == "dlms_cosem"
    assert payload["intent"] == "on_demand_read"
    assert payload["stages"] == ["iec62056_21", "hdlc", "dlms_cosem", "gurux_bridge"]
    assert payload["target"]["meter_id"] == meter_id
    assert payload["target"]["endpoint_assignment_id"] == endpoint_assignment_id
    assert payload["target"]["protocol_association_profile_id"] == protocol_profile_id
    assert payload["command"]["normalized_payload"]["obis"] == ["1.0.1.8.0.255"]
    assert payload["transport"]["endpoint_transport_type"] == "tcp_ip"
    assert payload["security"]["authentication_mode"] == "low"


def test_build_runtime_plan_stringifies_inet_endpoint_ip_address(
    client,
    db_session: Session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)
    assignment = db_session.get(MeterEndpointAssignment, UUID(endpoint_assignment_id))
    assert assignment is not None
    endpoint = assignment.endpoint
    assert endpoint is not None
    endpoint.host = None
    endpoint.ip_address = "127.0.0.1"
    db_session.add(endpoint)
    db_session.commit()
    db_session.refresh(endpoint)
    template_id = _create_command_template_record(client, token, "runtime-ip-address-only")

    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "endpoint_assignment_id": endpoint_assignment_id,
            "protocol_association_profile_id": protocol_profile_id,
            "idempotency_key": f"runtime-ip-{_suffix()}",
            "request_payload": {"obis": ["1.0.1.8.0.255"], "capture_mode": "current"},
        },
    )
    assert command_response.status_code == 201

    response = client.post(
        f"/api/v1/internal/commands/{command_response.json()['id']}/build-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transport"]["host"] is None
    assert payload["transport"]["ip_address"] == "127.0.0.1"


def test_reject_runtime_plan_when_connectivity_or_protocol_missing(client, db_session: Session) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    template_id = _create_command_template_record(client, token, "runtime-missing-connectivity")

    command_response = client.post(
        f"/api/v1/meters/{meter_id}/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "command_template_id": template_id,
            "idempotency_key": f"runtime-missing-{_suffix()}",
        },
    )
    assert command_response.status_code == 201

    response = client.post(
        f"/api/v1/internal/commands/{command_response.json()['id']}/build-runtime-plan",
        headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
    )

    assert response.status_code == 409
    assert "endpoint assignment" in response.json()["detail"].lower()


def test_normalized_result_contract_shapes_feed_existing_ingestion_requests() -> None:
    now = datetime.now(UTC)
    result = RuntimeCommandResult(
        outcome=RuntimeCommandOutcome.SUCCEEDED,
        result_summary={"register_count": 1},
        response_snapshot={"raw": "ok"},
        session_result=RuntimeSessionResult(
            status=ConnectivitySessionStatus.SUCCEEDED,
            session_purpose=ConnectivitySessionPurpose.MANUAL_DIAGNOSTIC,
            started_at=now,
            ended_at=now,
            correlation_id="corr-123",
            bytes_sent=128,
            bytes_received=512,
        ),
        reading_batch=RuntimeReadingBatchPayload(
            source_type=ReadingSourceType.COMMAND_RESULT,
            captured_at=now,
            received_at=now,
            status=ReadingBatchStatus.RECEIVED,
            readings=[
                RuntimeReadingPayload(
                    obis_code="1.0.1.8.0.255",
                    reading_type=ReadingType.REGISTER,
                    value_numeric="123.456",
                    unit="kWh",
                    captured_at=now,
                )
            ],
            register_snapshots=[
                RuntimeRegisterSnapshotPayload(
                    snapshot_type=SnapshotType.BILLING,
                    captured_at=now,
                    payload={"1.0.1.8.0.255": "123.456"},
                )
            ],
            load_profile_intervals=[
                RuntimeLoadProfileIntervalPayload(
                    channel_id=UUID("00000000-0000-0000-0000-000000000123"),
                    interval_start=now,
                    interval_end=now,
                    value_numeric="5.0",
                )
            ],
        ),
        events=[
            RuntimeEventPayload(
                event_code="POWER_RESTORE",
                event_name="Power Restore",
                severity=EventSeverity.INFO,
                    event_state=EventState.OPEN,
                occurred_at=now,
                normalized_payload={"state": "restored"},
            )
        ],
    )

    reading_request = to_reading_batch_ingest_request(result)
    event_request = to_meter_events_ingest_request(result)
    summary = to_command_result_summary(result)

    assert reading_request is not None
    assert reading_request.readings[0].obis_code == "1.0.1.8.0.255"
    assert reading_request.register_snapshots[0].snapshot_type == SnapshotType.BILLING
    assert reading_request.load_profile_intervals[0].channel_id.hex.endswith("123")
    assert event_request is not None
    assert event_request.events[0].event_code == "POWER_RESTORE"
    assert summary["outcome"] == "succeeded"
    assert summary["has_readings"] is True
    assert summary["event_count"] == 1


def test_command_template_category_maps_to_expected_runtime_intent() -> None:
    assert map_command_category_to_runtime_intent(CommandCategory.ON_DEMAND_READ).value == "on_demand_read"
    assert map_command_category_to_runtime_intent(CommandCategory.REMOTE_DISCONNECT).value == "disconnect"
    assert map_command_category_to_runtime_intent(CommandCategory.REMOTE_RECONNECT).value == "reconnect"
    assert map_command_category_to_runtime_intent(CommandCategory.CLOCK_SYNC).value == "clock_sync"
    assert map_command_category_to_runtime_intent(CommandCategory.PROFILE_CAPTURE).value == "read_profile"
    assert map_command_category_to_runtime_intent(CommandCategory.CONNECTIVITY_TEST).value == "connectivity_test"
    assert map_command_category_to_runtime_intent(CommandCategory.CONFIG_PUSH).value == "config_push"


def _attach_runtime_connectivity(db_session: Session, meter_id: str) -> tuple[str, str]:
    suffix = _suffix()
    meter_uuid = UUID(meter_id)
    endpoint = CommunicationEndpoint(
        code=f"runtime-endpoint-{suffix}",
        display_name="Runtime Endpoint",
        endpoint_type=CommunicationEndpointType.TCP,
        transport_type=ConnectivityTransportType.TCP_IP,
        host="10.10.10.10",
        port=4059,
        is_active=True,
    )
    db_session.add(endpoint)
    db_session.flush()

    assignment = MeterEndpointAssignment(
        meter_id=meter_uuid,
        endpoint_id=endpoint.id,
        is_primary=True,
        assignment_status=EndpointAssignmentStatus.ACTIVE,
    )
    db_session.add(assignment)

    profile = ProtocolAssociationProfile(
        code=f"runtime-profile-{suffix}",
        name="Runtime DLMS Profile",
        protocol_family=ProtocolFamily.DLMS_COSEM,
        iec62056_21_enabled=True,
        iec_device_address="A12345",
        iec_baud_rate=300,
        client_address=16,
        server_address=1,
        authentication_mode=AssociationAuthenticationMode.LOW,
        password_secret_ref="secret://meters/runtime-low",
        profile_settings={"association": "public-client"},
        is_active=True,
    )
    db_session.add(profile)

    communication_profile = CommunicationProfile(
        code=f"runtime-comm-{suffix}",
        name="Runtime Communication Profile",
        transport_type=TransportType.TCP_IP,
        ip_mode=IPMode.STATIC,
        port=4059,
        apn="hes-apn",
        authentication_mode=AuthenticationMode.NONE,
        protocol_settings={"wrapper": False},
        is_active=True,
    )
    db_session.add(communication_profile)
    db_session.flush()

    meter = db_session.get(Meter, meter_uuid)
    assert meter is not None
    meter.communication_profile_id = communication_profile.id
    db_session.add(meter)
    db_session.commit()
    return str(assignment.id), str(profile.id)


def _create_command_template_record(client, token: str, code: str) -> str:
    response = client.post(
        "/api/v1/command-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code,
            "name": code.replace("-", " ").title(),
            "category": "on_demand_read",
            "target_scope": "meter",
            "timeout_seconds": 120,
            "max_retries": 1,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_meter_record(client, token: str) -> str:
    suffix = _suffix()
    manufacturer_response = client.post(
        "/api/v1/manufacturers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Runtime Vendor {suffix}",
            "code": f"runtime-vendor-{suffix}",
            "country": "Oman",
            "is_active": True,
        },
    )
    assert manufacturer_response.status_code == 201
    manufacturer_id = manufacturer_response.json()["id"]

    model_response = client.post(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "manufacturer_id": manufacturer_id,
            "model_code": f"runtime-model-{suffix}",
            "display_name": "Runtime Model",
            "phase_type": "single_phase",
            "meter_category": "electricity",
            "dlms_capable": True,
            "is_active": True,
        },
    )
    assert model_response.status_code == 201

    meter_response = client.post(
        "/api/v1/meters",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "serial_number": f"RUNTIME-METER-{suffix}",
            "utility_meter_number": f"RUNTIME-UMN-{suffix}",
            "manufacturer_id": manufacturer_id,
            "meter_model_id": model_response.json()["id"],
            "current_status": "registered",
        },
    )
    assert meter_response.status_code == 201
    return meter_response.json()["id"]


def _suffix() -> str:
    return str(int(datetime.now(UTC).timestamp() * 1000))
