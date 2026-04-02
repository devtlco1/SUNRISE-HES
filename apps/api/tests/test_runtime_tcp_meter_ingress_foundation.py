from __future__ import annotations

import socket
import time
import uuid
from datetime import UTC, datetime

from app.modules.commands.enums import CommandCategory
from app.modules.connectivity.enums import (
    AssociationAuthenticationMode,
    ConnectivityTransportType,
    ProtocolFamily,
)
from app.modules.connectivity.models import MeterEndpointAssignment
from app.modules.jobs.dependencies import INTERNAL_TOKEN_HEADER
from app.runtime.adapters.dlms_cosem import GuruxDlmsAdapterBridge
from app.runtime.adapters.gurux_tcp_ingress import LiveTcpOnDemandReadExecution
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

