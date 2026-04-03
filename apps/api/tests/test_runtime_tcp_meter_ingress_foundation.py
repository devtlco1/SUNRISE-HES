from __future__ import annotations

import socket
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.modules.commands.enums import CommandCategory
from app.modules.connectivity.enums import (
    AssociationAuthenticationMode,
    ConnectivityTransportType,
    ProtocolFamily,
)
from app.modules.connectivity.models import CommunicationEndpoint, MeterEndpointAssignment
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.modules.meters.models import Meter
from app.runtime.adapters.dlms_cosem import GuruxDlmsAdapterBridge
from app.runtime.adapters.gurux_tcp_ingress import (
    LiveTcpIdentityDiscoveryExecution,
    LiveTcpOnDemandReadExecution,
)
from app.runtime.contracts import (
    MeterRuntimeTarget,
    RuntimeExecutionContext,
    RuntimeOnDemandReadAdapterRequest,
    RuntimeOnDemandReadOperation,
    RuntimeSecurityMaterialRefs,
    RuntimeTransportConfig,
)
from app.runtime.contracts.runtime_execution_session import RuntimeExecutionSessionLineage
from app.runtime.services import tcp_meter_ingress
from tests.test_protocol_runtime_foundation import (
    _attach_runtime_connectivity,
    _create_meter_record,
    _login_as_super_admin,
)


def _wait_until(predicate, *, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for runtime TCP meter ingress condition.")


def test_tcp_meter_ingress_manager_tracks_listener_connection_and_binding() -> None:
    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listening_status = manager.get_status()
        assert listening_status.listening is True
        assert listening_status.connected is False
        assert listening_status.listen_port is not None

        client_socket = socket.create_connection(
            ("127.0.0.1", listening_status.listen_port),
            timeout=1.0,
        )
        _wait_until(lambda: manager.get_status().connected is True)

        meter_id = uuid.uuid4()
        endpoint_id = uuid.uuid4()
        manager.bind_active_connection(meter_id=meter_id, endpoint_id=endpoint_id)
        bound_status = manager.get_status()
        assert bound_status.connected is True
        assert bound_status.bound_meter_id == meter_id
        assert bound_status.bound_endpoint_id == endpoint_id
        assert bound_status.active_connection_id is not None

        with manager.borrow_bound_connection(meter_id=meter_id, endpoint_id=endpoint_id) as borrowed:
            assert borrowed is not None
            assert borrowed.bound_meter_id == meter_id
            assert manager.get_status().connection_in_use is True

        assert manager.get_status().connection_in_use is False
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_routes_surface_status_and_binding(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = uuid.UUID(_create_meter_record(client, token))
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(
        db_session,
        str(meter_id),
    )
    assignment = db_session.get(MeterEndpointAssignment, uuid.UUID(endpoint_assignment_id))
    assert assignment is not None

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        status_response = client.get(
            "/api/v1/internal/platform/tcp-meter-ingress/status",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["result"]["connected"] is True

        bind_response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/bind-active-connection",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={
                "meter_id": str(meter_id),
                "endpoint_id": str(assignment.endpoint_id),
                "protocol_association_profile_id": protocol_profile_id,
            },
        )
        assert bind_response.status_code == 200
        payload = bind_response.json()["result"]
        assert payload["bound_meter_id"] == str(meter_id)
        assert payload["bound_endpoint_id"] == str(assignment.endpoint_id)
        assert payload["bound_protocol_association_profile_id"] == protocol_profile_id
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_bind_resolves_primary_assignment_when_endpoint_omitted(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = uuid.UUID(_create_meter_record(client, token))
    endpoint_assignment_id, protocol_profile_id = _attach_runtime_connectivity(
        db_session,
        str(meter_id),
    )
    assignment = db_session.get(MeterEndpointAssignment, uuid.UUID(endpoint_assignment_id))
    assert assignment is not None

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        bind_response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/bind-active-connection",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={
                "meter_id": str(meter_id),
                "protocol_association_profile_id": protocol_profile_id,
            },
        )
        assert bind_response.status_code == 200
        payload = bind_response.json()["result"]
        assert payload["bound_meter_id"] == str(meter_id)
        assert payload["bound_endpoint_id"] == str(assignment.endpoint_id)
        assert payload["bound_protocol_association_profile_id"] == protocol_profile_id
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_on_demand_read_adapter_uses_bound_live_tcp_ingress_connection(monkeypatch) -> None:
    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        meter_id = uuid.uuid4()
        endpoint_id = uuid.uuid4()
        profile_id = uuid.uuid4()
        manager.bind_active_connection(
            meter_id=meter_id,
            endpoint_id=endpoint_id,
            protocol_association_profile_id=profile_id,
        )

        def fake_execute_billing_snapshot_over_tcp_ingress(*, sock, config, obis_codes):
            assert sock is not None
            assert config.start_protocol == "iec62056_21"
            assert obis_codes == ["1.0.1.8.0.255"]
            return LiveTcpOnDemandReadExecution(
                register_snapshot_payload={"1.0.1.8.0.255": "456.789"},
                protocol_trace={"start_protocol": config.start_protocol},
                raw_frames=[{"stage": "fake"}],
                bytes_sent=12,
                bytes_received=34,
            )

        monkeypatch.setattr(
            "app.runtime.adapters.dlms_cosem.execute_billing_snapshot_over_tcp_ingress",
            fake_execute_billing_snapshot_over_tcp_ingress,
        )

        result = GuruxDlmsAdapterBridge().execute_on_demand_read(
            RuntimeOnDemandReadAdapterRequest(
                adapter_key="gurux-dlms-bridge",
                protocol_family=ProtocolFamily.DLMS_COSEM,
                operation=RuntimeOnDemandReadOperation.READ_BILLING_SNAPSHOT,
                command_category=CommandCategory.ON_DEMAND_READ,
                execution_context=RuntimeExecutionContext(
                    command_id=uuid.uuid4(),
                    job_run_id=uuid.uuid4(),
                    command_attempt_id=uuid.uuid4(),
                    correlation_id="corr-live-tcp",
                    worker_identifier="worker-runtime-live-tcp",
                    request_id="request-live-tcp",
                    triggered_at=datetime.now(UTC),
                ),
                target=MeterRuntimeTarget(
                    meter_id=meter_id,
                    serial_number="meter-live-001",
                    utility_meter_number="utility-live-001",
                    meter_profile_id=None,
                    manufacturer_code="SUN",
                    meter_model_code="ST34",
                    meter_model_name="Sunrise Test Meter",
                    endpoint_assignment_id=uuid.uuid4(),
                    endpoint_id=endpoint_id,
                    endpoint_code="live-endpoint",
                    protocol_association_profile_id=profile_id,
                ),
                transport=RuntimeTransportConfig(
                    endpoint_transport_type=ConnectivityTransportType.TCP_IP,
                    host="127.0.0.1",
                    port=listen_port,
                ),
                security=RuntimeSecurityMaterialRefs(
                    authentication_mode=AssociationAuthenticationMode.NONE,
                ),
                protocol_profile_code="dlms-live-tcp",
                iec62056_21_enabled=True,
                iec_device_address=None,
                iec_baud_rate=300,
                client_address=1,
                server_address=1,
                server_address_size=4,
                protocol_settings={"tcp_start_protocol": "iec", "use_broadcast_snrm_first": True},
                protocol_defaults=None,
                request_payload={"obis": ["1.0.1.8.0.255"]},
                normalized_payload={"obis": ["1.0.1.8.0.255"]},
                dispatch_envelope_record_id="dispatch-live-tcp",
                trace_references={
                    "session_identifier": "session-live-tcp",
                    "delivery_contract_record_id": "delivery-live-tcp",
                    "envelope_record_id": "envelope-live-tcp",
                    "publication_contract_record_id": "publication-live-tcp",
                    "attestation_record_id": "attestation-live-tcp",
                    "settlement_record_id": "settlement-live-tcp",
                    "reconciliation_record_id": "reconciliation-live-tcp",
                    "interpretation_record_id": "interpretation-live-tcp",
                    "observation_record_id": "observation-live-tcp",
                    "invocation_result_record_id": "invocation-live-tcp",
                    "dispatch_request_record_id": "dispatch-request-live-tcp",
                    "selection_record_id": "selection-live-tcp",
                    "intent_record_id": "intent-live-tcp",
                    "closure_record_id": "closure-live-tcp",
                    "materialization_record_id": "materialization-live-tcp",
                    "post_processing_record_id": "post-processing-live-tcp",
                    "disposition_record_id": "disposition-live-tcp",
                    "outcome_record_id": "outcome-live-tcp",
                },
                lineage=RuntimeExecutionSessionLineage(
                    dispatch_request_identity="dispatch-identity-live-tcp",
                    queue_message_id="queue-live-tcp",
                    claim_token="claim-live-tcp",
                    intended_worker_path="runtime-live-tcp",
                ),
            )
        )

        assert result.execution_outcome.value == "succeeded"
        assert result.register_snapshot is not None
        assert result.register_snapshot.payload["1.0.1.8.0.255"] == "456.789"
        assert result.adapter_result_summary["live_tcp_ingress"] is True
        assert result.adapter_result_summary["bytes_sent"] == 12
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_discovery_refuses_without_active_connection(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    try:
        response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/discover-identity",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert response.status_code == 409
        assert "no active live connection" in response.json()["detail"].lower()
    finally:
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_discovery_returns_identity_before_bind(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setenv("RUNTIME_SECRET_SECRET___METERS_RUNTIME_LOW", "test-runtime-password")
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        def fake_execute_identity_discovery_over_tcp_ingress(*, sock, config, identity_obis_codes=None):
            assert sock is not None
            assert config.start_protocol == "iec62056_21"
            return LiveTcpIdentityDiscoveryExecution(
                identity_obis_code="0.0.96.1.0.255",
                identity_value="SN-123456",
                identity_values={
                    "0.0.96.1.0.255": "SN-123456",
                    "0.0.96.1.1.255": "DEVICE-ABC",
                },
                protocol_trace={"association_method": "broadcast_snrm_then_aarq"},
                raw_frames=[{"stage": "fake-discovery"}],
                bytes_sent=22,
                bytes_received=44,
            )

        monkeypatch.setattr(
            "app.runtime.services.tcp_meter_identity_discovery.execute_identity_discovery_over_tcp_ingress",
            fake_execute_identity_discovery_over_tcp_ingress,
        )

        response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/discover-identity",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert response.status_code == 200
        payload = response.json()["result"]
        assert payload["success"] is True
        assert payload["discovered_identity_value"] == "SN-123456"
        assert payload["discovered_identity_obis_code"] == "0.0.96.1.0.255"
        assert payload["identity_values"]["0.0.96.1.1.255"] == "DEVICE-ABC"
        assert payload["protocol_path_used"] == "broadcast_snrm_then_aarq"
        assert payload["active_connection_id"] is not None
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_discovery_respects_connection_in_use(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        with manager.borrow_active_unbound_connection() as borrowed:
            assert borrowed is not None
            response = client.post(
                "/api/v1/internal/platform/tcp-meter-ingress/discover-identity",
                headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
                json={"protocol_association_profile_id": protocol_profile_id},
            )
            assert response.status_code == 409
            assert "already in use" in response.json()["detail"].lower()
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_persist_refuses_without_active_connection(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    try:
        response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/persist-discovered-meter",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert response.status_code == 409
        assert "no active live connection" in response.json()["detail"].lower()
    finally:
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_persist_matches_existing_meter_without_duplicate(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    existing_meter_id = uuid.UUID(_create_meter_record(client, token))
    existing_assignment_id, protocol_profile_id = _attach_runtime_connectivity(
        db_session,
        str(existing_meter_id),
    )
    existing_assignment = db_session.get(MeterEndpointAssignment, uuid.UUID(existing_assignment_id))
    assert existing_assignment is not None
    existing_meter = db_session.get(Meter, existing_meter_id)
    assert existing_meter is not None
    existing_meter.serial_number = "SN-MATCH-001"
    db_session.add(existing_meter)
    db_session.commit()

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setenv("RUNTIME_SECRET_SECRET___METERS_RUNTIME_LOW", "test-runtime-password")
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        def fake_execute_identity_discovery_over_tcp_ingress(*, sock, config, identity_obis_codes=None):
            assert sock is not None
            return LiveTcpIdentityDiscoveryExecution(
                identity_obis_code="0.0.96.1.0.255",
                identity_value="SN-MATCH-001",
                identity_values={"0.0.96.1.0.255": "SN-MATCH-001"},
                protocol_trace={"association_method": "broadcast_snrm_then_aarq"},
                raw_frames=[{"stage": "fake-discovery"}],
                bytes_sent=15,
                bytes_received=31,
            )

        monkeypatch.setattr(
            "app.runtime.services.tcp_meter_identity_discovery.execute_identity_discovery_over_tcp_ingress",
            fake_execute_identity_discovery_over_tcp_ingress,
        )

        response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/persist-discovered-meter",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert response.status_code == 200
        payload = response.json()["result"]
        assert payload["success"] is True
        assert payload["matched_existing_meter"] is True
        assert payload["created_meter"] is False
        assert payload["created_endpoint"] is True
        assert payload["created_assignment"] is True
        assert payload["meter_id"] == str(existing_meter_id)
        assert payload["communication_endpoint_id"] != str(existing_assignment.endpoint_id)

        matched_meter_count = db_session.scalar(
            select(func.count())
            .select_from(Meter)
            .where(func.lower(Meter.serial_number) == "sn-match-001")
        )
        assert matched_meter_count == 1
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_persist_creates_new_meter_endpoint_and_assignment(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    seed_meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, seed_meter_id)

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setenv("RUNTIME_SECRET_SECRET___METERS_RUNTIME_LOW", "test-runtime-password")
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        def fake_execute_identity_discovery_over_tcp_ingress(*, sock, config, identity_obis_codes=None):
            assert sock is not None
            return LiveTcpIdentityDiscoveryExecution(
                identity_obis_code="0.0.96.1.0.255",
                identity_value="SN-NEW-INGRESS-001",
                identity_values={"0.0.96.1.0.255": "SN-NEW-INGRESS-001"},
                protocol_trace={"association_method": "broadcast_snrm_then_aarq"},
                raw_frames=[{"stage": "fake-discovery"}],
                bytes_sent=18,
                bytes_received=27,
            )

        monkeypatch.setattr(
            "app.runtime.services.tcp_meter_identity_discovery.execute_identity_discovery_over_tcp_ingress",
            fake_execute_identity_discovery_over_tcp_ingress,
        )

        response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/persist-discovered-meter",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert response.status_code == 200
        payload = response.json()["result"]
        assert payload["success"] is True
        assert payload["matched_existing_meter"] is False
        assert payload["created_meter"] is True
        assert payload["created_endpoint"] is True
        assert payload["created_assignment"] is True
        assert payload["discovered_identity_value"] == "SN-NEW-INGRESS-001"

        created_meter = db_session.get(Meter, uuid.UUID(payload["meter_id"]))
        assert created_meter is not None
        assert created_meter.serial_number == "SN-NEW-INGRESS-001"
        assert created_meter.notes is not None
        assert "auto-registered from live tcp ingress identity discovery" in created_meter.notes.lower()

        created_endpoint = db_session.get(
            CommunicationEndpoint,
            uuid.UUID(payload["communication_endpoint_id"]),
        )
        assert created_endpoint is not None
        assert created_endpoint.host == "127.0.0.1"

        created_assignment = db_session.get(
            MeterEndpointAssignment,
            uuid.UUID(payload["assignment_id"]),
        )
        assert created_assignment is not None
        assert created_assignment.meter_id == created_meter.id
        assert created_assignment.endpoint_id == created_endpoint.id
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_persist_is_duplicate_safe_on_repeat_calls(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    seed_meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, seed_meter_id)

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setenv("RUNTIME_SECRET_SECRET___METERS_RUNTIME_LOW", "test-runtime-password")
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        def fake_execute_identity_discovery_over_tcp_ingress(*, sock, config, identity_obis_codes=None):
            assert sock is not None
            return LiveTcpIdentityDiscoveryExecution(
                identity_obis_code="0.0.96.1.0.255",
                identity_value="SN-REPEAT-001",
                identity_values={"0.0.96.1.0.255": "SN-REPEAT-001"},
                protocol_trace={"association_method": "broadcast_snrm_then_aarq"},
                raw_frames=[{"stage": "fake-discovery"}],
                bytes_sent=21,
                bytes_received=29,
            )

        monkeypatch.setattr(
            "app.runtime.services.tcp_meter_identity_discovery.execute_identity_discovery_over_tcp_ingress",
            fake_execute_identity_discovery_over_tcp_ingress,
        )

        first_response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/persist-discovered-meter",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert first_response.status_code == 200
        first_payload = first_response.json()["result"]
        assert first_payload["created_meter"] is True
        assert first_payload["created_endpoint"] is True
        assert first_payload["created_assignment"] is True

        second_response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/persist-discovered-meter",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert second_response.status_code == 200
        second_payload = second_response.json()["result"]
        assert second_payload["matched_existing_meter"] is True
        assert second_payload["created_meter"] is False
        assert second_payload["created_endpoint"] is False
        assert second_payload["created_assignment"] is False
        assert second_payload["meter_id"] == first_payload["meter_id"]
        assert second_payload["communication_endpoint_id"] == first_payload["communication_endpoint_id"]
        assert second_payload["assignment_id"] == first_payload["assignment_id"]

        meter_count = db_session.scalar(
            select(func.count())
            .select_from(Meter)
            .where(func.lower(Meter.serial_number) == "sn-repeat-001")
        )
        assignment_count = db_session.scalar(
            select(func.count())
            .select_from(MeterEndpointAssignment)
            .where(MeterEndpointAssignment.id == uuid.UUID(first_payload["assignment_id"]))
        )
        endpoint_count = db_session.scalar(
            select(func.count())
            .select_from(CommunicationEndpoint)
            .where(CommunicationEndpoint.id == uuid.UUID(first_payload["communication_endpoint_id"]))
        )
        assert meter_count == 1
        assert assignment_count == 1
        assert endpoint_count == 1
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()


def test_internal_runtime_tcp_meter_ingress_persist_refuses_when_discovery_has_no_identity(
    client,
    monkeypatch,
    db_session,
) -> None:
    token = _login_as_super_admin(client, db_session)
    meter_id = _create_meter_record(client, token)
    _, protocol_profile_id = _attach_runtime_connectivity(db_session, meter_id)

    manager = tcp_meter_ingress.TcpMeterIngressManager(
        enabled=True,
        host="127.0.0.1",
        port=0,
        socket_timeout_seconds=0.2,
    )
    monkeypatch.setenv("RUNTIME_SECRET_SECRET___METERS_RUNTIME_LOW", "test-runtime-password")
    monkeypatch.setattr(tcp_meter_ingress, "_tcp_meter_ingress_manager", manager)
    manager.start()
    client_socket: socket.socket | None = None
    try:
        _wait_until(lambda: manager.get_status().listen_port is not None)
        listen_port = manager.get_status().listen_port
        assert listen_port is not None
        client_socket = socket.create_connection(("127.0.0.1", listen_port), timeout=1.0)
        _wait_until(lambda: manager.get_status().connected is True)

        def fake_execute_identity_discovery_over_tcp_ingress(*, sock, config, identity_obis_codes=None):
            assert sock is not None
            return LiveTcpIdentityDiscoveryExecution(
                identity_obis_code=None,
                identity_value=None,
                identity_values={},
                protocol_trace={"association_method": "broadcast_snrm_then_aarq"},
                raw_frames=[{"stage": "fake-discovery"}],
                bytes_sent=17,
                bytes_received=18,
            )

        monkeypatch.setattr(
            "app.runtime.services.tcp_meter_identity_discovery.execute_identity_discovery_over_tcp_ingress",
            fake_execute_identity_discovery_over_tcp_ingress,
        )

        response = client.post(
            "/api/v1/internal/platform/tcp-meter-ingress/persist-discovered-meter",
            headers={INTERNAL_TOKEN_HEADER: "test-internal-token"},
            json={"protocol_association_profile_id": protocol_profile_id},
        )
        assert response.status_code == 409
        assert "usable unique meter identity" in response.json()["detail"].lower()
    finally:
        if client_socket is not None:
            client_socket.close()
        manager.stop()

