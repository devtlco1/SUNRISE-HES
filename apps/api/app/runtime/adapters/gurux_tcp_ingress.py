from __future__ import annotations

from dataclasses import dataclass, field
import logging
import socket
import time
from typing import Any, Literal


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveTcpDlmsSessionConfig:
    start_protocol: Literal["iec62056_21", "dlms"]
    client_address: int
    server_address: int
    server_address_size: int
    authentication_mode: str
    password: str | None
    iec_ack_hex_candidates: list[str] = field(
        default_factory=lambda: ["063235320D0A", "06B235B28D0A"]
    )
    use_broadcast_snrm_first: bool = True
    broadcast_snrm_hex: str = "7EA00AFEFEFEFF0393C9837E"
    after_iec_sleep_ms: int = 1200
    dlms_read_timeout_seconds: float = 2.5
    iec_serial_timeout_seconds: float = 5.0
    iec_wake_zero_bytes: int = 0
    iec_wake_post_delay_ms: int = 0
    iec_ident_retries: int = 4
    iec_ident_retry_delay_ms: int = 350
    before_first_iec_send_delay_ms: int = 0
    ua_swap_addresses: bool = False
    send_hdlc_disc_before_close: bool = True
    disc_drain_timeout_seconds: float = 0.4


@dataclass(frozen=True)
class LiveTcpOnDemandReadExecution:
    register_snapshot_payload: dict[str, str]
    protocol_trace: dict[str, object]
    raw_frames: list[dict[str, object]]
    bytes_sent: int
    bytes_received: int


@dataclass(frozen=True)
class LiveTcpIdentityDiscoveryExecution:
    identity_obis_code: str | None
    identity_value: str | None
    identity_values: dict[str, str]
    protocol_trace: dict[str, object]
    raw_frames: list[dict[str, object]]
    bytes_sent: int
    bytes_received: int


@dataclass(frozen=True)
class LiveTcpRelayControlStateObservation:
    control_state: str | None
    output_state: bool | None
    control_state_error: str | None = None
    output_state_error: str | None = None


@dataclass(frozen=True)
class LiveTcpRelayControlExecution:
    invocation_status: str
    before_state: LiveTcpRelayControlStateObservation | None
    after_state: LiveTcpRelayControlStateObservation | None
    error_detail: str | None
    protocol_trace: dict[str, object]
    raw_frames: list[dict[str, object]]
    bytes_sent: int
    bytes_received: int


IDENTITY_DISCOVERY_OBIS_CODES = [
    "0.0.96.1.0.255",
    "0.0.96.1.1.255",
    "0.0.96.1.2.255",
]


class SocketSerialAdapter:
    """Match the small serial-like API the Gurux workflow expects."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._timeout: float | None = None
        self.bytes_sent = 0
        self.bytes_received = 0

    @property
    def timeout(self) -> float | None:
        try:
            return self.sock.gettimeout()
        except OSError:
            return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = value
        self.sock.settimeout(value)

    def write(self, data: bytes) -> int:
        self.sock.sendall(data)
        self.bytes_sent += len(data)
        return len(data)

    def flush(self) -> None:
        return None

    def read(self, size: int) -> bytes:
        try:
            data = self.sock.recv(size)
        except socket.timeout:
            return b""
        except BlockingIOError:
            return b""
        self.bytes_received += len(data)
        return data or b""

    def reset_input_buffer(self) -> None:
        previous_timeout = self.timeout
        try:
            self.sock.settimeout(0.01)
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.bytes_received += len(chunk)
        except (socket.timeout, BlockingIOError):
            pass
        finally:
            if previous_timeout is not None:
                self.sock.settimeout(previous_timeout)

    def reset_output_buffer(self) -> None:
        return None


def execute_billing_snapshot_over_tcp_ingress(
    *,
    sock: socket.socket,
    config: LiveTcpDlmsSessionConfig,
    obis_codes: list[str],
) -> LiveTcpOnDemandReadExecution:
    if not obis_codes:
        raise ValueError("Live TCP ingress execution requires at least one OBIS code.")

    transport = SocketSerialAdapter(sock)
    raw_frames: list[dict[str, object]] = []

    if config.start_protocol == "iec62056_21":
        transport.timeout = float(config.iec_serial_timeout_seconds)
        handshake_ok, handshake_details, handshake_frames = _run_iec_handshake_tcp(transport, config)
        raw_frames.extend(handshake_frames)
        if not handshake_ok:
            raise RuntimeError(handshake_details.get("error", "IEC handshake failed."))
        time.sleep(config.after_iec_sleep_ms / 1000.0)

    transport.timeout = float(config.dlms_read_timeout_seconds)
    if config.use_broadcast_snrm_first:
        associated, association_details, association_frames, client = _attempt_vendor_broadcast_association(
            transport,
            config,
        )
    else:
        associated, association_details, association_frames, client = _attempt_gurux_association(
            transport,
            config,
        )
    raw_frames.extend(association_frames)
    if not associated or client is None:
        raise RuntimeError(association_details.get("error", "DLMS association failed."))

    try:
        register_snapshot_payload = _read_obis_via_gurux(
            transport,
            client,
            obis_codes,
            config,
        )
    finally:
        _try_gurux_disconnect(transport, client, config)

    return LiveTcpOnDemandReadExecution(
        register_snapshot_payload=register_snapshot_payload,
        protocol_trace={
            "start_protocol": config.start_protocol,
            "association_method": (
                "broadcast_snrm_then_aarq" if config.use_broadcast_snrm_first else "snrm_then_aarq"
            ),
            "obis_count": len(obis_codes),
            "association_details": association_details,
        },
        raw_frames=raw_frames,
        bytes_sent=transport.bytes_sent,
        bytes_received=transport.bytes_received,
    )


def execute_identity_discovery_over_tcp_ingress(
    *,
    sock: socket.socket,
    config: LiveTcpDlmsSessionConfig,
    identity_obis_codes: list[str] | None = None,
) -> LiveTcpIdentityDiscoveryExecution:
    obis_codes = identity_obis_codes or list(IDENTITY_DISCOVERY_OBIS_CODES)
    if not obis_codes:
        raise ValueError("Live TCP identity discovery requires at least one OBIS code.")

    transport = SocketSerialAdapter(sock)
    raw_frames: list[dict[str, object]] = []

    if config.start_protocol == "iec62056_21":
        transport.timeout = float(config.iec_serial_timeout_seconds)
        handshake_ok, handshake_details, handshake_frames = _run_iec_handshake_tcp(transport, config)
        raw_frames.extend(handshake_frames)
        if not handshake_ok:
            raise RuntimeError(handshake_details.get("error", "IEC handshake failed."))
        time.sleep(config.after_iec_sleep_ms / 1000.0)

    transport.timeout = float(config.dlms_read_timeout_seconds)
    if config.use_broadcast_snrm_first:
        associated, association_details, association_frames, client = _attempt_vendor_broadcast_association(
            transport,
            config,
        )
    else:
        associated, association_details, association_frames, client = _attempt_gurux_association(
            transport,
            config,
        )
    raw_frames.extend(association_frames)
    if not associated or client is None:
        raise RuntimeError(association_details.get("error", "DLMS association failed."))

    try:
        identity_values = _read_obis_via_gurux(
            transport,
            client,
            obis_codes,
            config,
        )
    finally:
        _try_gurux_disconnect(transport, client, config)

    identity_obis_code: str | None = None
    identity_value: str | None = None
    for obis_code in obis_codes:
        candidate = identity_values.get(obis_code)
        if candidate:
            identity_obis_code = obis_code
            identity_value = candidate
            break

    return LiveTcpIdentityDiscoveryExecution(
        identity_obis_code=identity_obis_code,
        identity_value=identity_value,
        identity_values=identity_values,
        protocol_trace={
            "start_protocol": config.start_protocol,
            "association_method": (
                "broadcast_snrm_then_aarq" if config.use_broadcast_snrm_first else "snrm_then_aarq"
            ),
            "obis_count": len(obis_codes),
            "association_details": association_details,
        },
        raw_frames=raw_frames,
        bytes_sent=transport.bytes_sent,
        bytes_received=transport.bytes_received,
    )


def execute_relay_control_over_tcp_ingress(
    *,
    sock: socket.socket,
    config: LiveTcpDlmsSessionConfig,
    relay_obis_code: str,
    operation_name: str,
) -> LiveTcpRelayControlExecution:
    if not relay_obis_code.strip():
        raise ValueError("Live TCP relay control requires a target OBIS code.")

    transport = SocketSerialAdapter(sock)
    raw_frames: list[dict[str, object]] = []

    if config.start_protocol == "iec62056_21":
        transport.timeout = float(config.iec_serial_timeout_seconds)
        handshake_ok, handshake_details, handshake_frames = _run_iec_handshake_tcp(transport, config)
        raw_frames.extend(handshake_frames)
        if not handshake_ok:
            raise RuntimeError(handshake_details.get("error", "IEC handshake failed."))
        time.sleep(config.after_iec_sleep_ms / 1000.0)

    transport.timeout = float(config.dlms_read_timeout_seconds)
    if config.use_broadcast_snrm_first:
        associated, association_details, association_frames, client = _attempt_vendor_broadcast_association(
            transport,
            config,
        )
    else:
        associated, association_details, association_frames, client = _attempt_gurux_association(
            transport,
            config,
        )
    raw_frames.extend(association_frames)
    if not associated or client is None:
        raise RuntimeError(association_details.get("error", "DLMS association failed."))

    before_state: LiveTcpRelayControlStateObservation | None = None
    after_state: LiveTcpRelayControlStateObservation | None = None
    invocation_status = "failed"
    error_detail: str | None = None
    try:
        before_state = _read_disconnect_control_state(
            transport,
            client,
            relay_obis_code=relay_obis_code,
            config=config,
        )
        try:
            _invoke_relay_control_via_gurux(
                transport,
                client,
                relay_obis_code=relay_obis_code,
                operation_name=operation_name,
                config=config,
            )
        except RuntimeError as exc:
            invocation_status = "rejected"
            error_detail = str(exc)
        after_state = _read_disconnect_control_state(
            transport,
            client,
            relay_obis_code=relay_obis_code,
            config=config,
        )
        if invocation_status != "rejected":
            invocation_status, error_detail = _interpret_relay_control_state_transition(
                operation_name=operation_name,
                before_state=before_state,
                after_state=after_state,
            )
    finally:
        _try_gurux_disconnect(transport, client, config)

    return LiveTcpRelayControlExecution(
        invocation_status=invocation_status,
        before_state=before_state,
        after_state=after_state,
        error_detail=error_detail,
        protocol_trace={
            "start_protocol": config.start_protocol,
            "association_method": (
                "broadcast_snrm_then_aarq" if config.use_broadcast_snrm_first else "snrm_then_aarq"
            ),
            "used_bound_connection": True,
            "relay_obis_code": relay_obis_code,
            "operation_name": operation_name,
            "association_details": association_details,
            "before_state": before_state.__dict__ if before_state is not None else None,
            "after_state": after_state.__dict__ if after_state is not None else None,
            "error_detail": error_detail,
        },
        raw_frames=raw_frames,
        bytes_sent=transport.bytes_sent,
        bytes_received=transport.bytes_received,
    )


def _run_iec_handshake_tcp(
    transport: SocketSerialAdapter,
    config: LiveTcpDlmsSessionConfig,
) -> tuple[bool, dict[str, object], list[dict[str, object]]]:
    frames: list[dict[str, object]] = []
    request = b"/?!\r\n"
    ack_candidates: list[bytes] = []
    for candidate in config.iec_ack_hex_candidates:
        try:
            ack_candidates.append(bytes.fromhex(candidate))
        except ValueError:
            continue

    if config.before_first_iec_send_delay_ms > 0:
        time.sleep(config.before_first_iec_send_delay_ms / 1000.0)

    if config.iec_wake_zero_bytes > 0:
        wake = b"\x00" * int(config.iec_wake_zero_bytes)
        transport.write(wake)
        transport.flush()
        time.sleep(config.iec_wake_post_delay_ms / 1000.0)

    ident = b""
    ident_ascii = ""
    for attempt in range(max(1, int(config.iec_ident_retries))):
        transport.reset_input_buffer()
        transport.write(request)
        transport.flush()
        ident = transport.read(512)
        frames.append(
            {
                "stage": f"iec_ident_{attempt + 1}",
                "tx_hex": request.hex(),
                "rx_hex": ident.hex(),
            }
        )
        if ident:
            ident_ascii = ident.decode("ascii", errors="replace").strip()
            break
        time.sleep(config.iec_ident_retry_delay_ms / 1000.0)

    if not ident:
        return False, {"error": "IEC TCP identification failed (no response to /?!)."}, frames

    ack_sent = False
    for ack in ack_candidates:
        transport.write(ack)
        transport.flush()
        frames.append({"stage": "iec_ack", "tx_hex": ack.hex()})
        ack_sent = True
        break

    return True, {"ident": ident_ascii, "ack_sent": ack_sent}, frames


def _attempt_vendor_broadcast_association(
    transport: SocketSerialAdapter,
    config: LiveTcpDlmsSessionConfig,
) -> tuple[bool, dict[str, object], list[dict[str, object]], Any]:
    from gurux_dlms.GXByteBuffer import GXByteBuffer
    from gurux_dlms.GXDLMSClient import GXDLMSClient

    frames: list[dict[str, object]] = []
    snrm = bytes.fromhex(config.broadcast_snrm_hex)
    transport.reset_input_buffer()
    transport.write(snrm)
    transport.flush()
    ua = _read_hdlc_frame(transport, max_wait=config.dlms_read_timeout_seconds)
    frames.append({"stage": "broadcast_snrm_ua", "tx_hex": snrm.hex(), "rx_hex": ua.hex()})

    parsed = _parse_ua_dlms_addresses(ua)
    if parsed is None:
        return False, {"error": "UA parse failed (HDLC addresses not found)."}, frames, None

    server_raw, client_raw = parsed
    if config.ua_swap_addresses:
        server_raw, client_raw = client_raw, server_raw
    gurux_client = _client_raw_to_gurux_logical(client_raw)
    gurux_server = _raw_hdlc_server_to_gurux_logical(
        server_raw,
        preferred_server_address_size=config.server_address_size,
    )
    auth = _resolve_gurux_authentication(config.authentication_mode)
    password = config.password or ""

    try:
        try:
            client = GXDLMSClient(
                True,
                int(gurux_client),
                int(gurux_server),
                auth,
                password,
                _resolve_gurux_interface_type(),
            )
        except TypeError:
            client = GXDLMSClient(
                int(gurux_client),
                int(gurux_server),
                auth,
                password,
                _resolve_gurux_interface_type(),
            )
        _call_if_exists(client, ["setServerAddressSize"], int(config.server_address_size))
        ua_info = _extract_ua_information_field(ua)
        if not ua_info:
            return False, {"error": "UA information field extraction failed."}, frames, None
        client.parseUAResponse(GXByteBuffer(ua_info))
        aare_reply = _send_pdu_list(transport, client, _get_req_frames(client, ["aarqRequest", "AARQRequest"]), config)
        if not aare_reply or not aare_reply.isComplete():
            return False, {"error": "AARQ did not complete over live TCP ingress."}, frames, None
        client.parseAareResponse(aare_reply.data)
        return (
            True,
            {
                "method": "broadcast_snrm_then_aarq",
                "wire_hdlc_client_hex": client_raw.hex(),
                "wire_hdlc_server_hex": server_raw.hex(),
                "gurux_client": int(gurux_client),
                "gurux_server": int(gurux_server),
            },
            frames,
            client,
        )
    except Exception as exc:  # noqa: BLE001
        frames.append({"stage": "assoc_exception", "error": repr(exc)})
        return False, {"error": "Association failed (broadcast SNRM + AARQ)."}, frames, None


def _attempt_gurux_association(
    transport: SocketSerialAdapter,
    config: LiveTcpDlmsSessionConfig,
) -> tuple[bool, dict[str, object], list[dict[str, object]], Any]:
    from gurux_dlms.GXDLMSClient import GXDLMSClient

    frames: list[dict[str, object]] = []
    auth = _resolve_gurux_authentication(config.authentication_mode)
    password = config.password or ""
    server_address = int(config.server_address)

    try:
        try:
            client = GXDLMSClient(
                True,
                int(config.client_address),
                server_address,
                auth,
                password,
                _resolve_gurux_interface_type(),
            )
        except TypeError:
            client = GXDLMSClient(
                int(config.client_address),
                server_address,
                auth,
                password,
                _resolve_gurux_interface_type(),
            )
        _call_if_exists(client, ["setServerAddressSize"], int(config.server_address_size))

        snrm_frames = _get_req_frames(client, ["snrmRequest", "SNRMRequest"])
        for index, frame in enumerate(snrm_frames):
            tx = _frameify(frame)
            transport.write(tx)
            transport.flush()
            rx = transport.read(1024)
            if rx:
                frames.append({"stage": f"snrm_{index}", "tx_hex": tx.hex(), "rx_hex": rx.hex()})
                _call_if_exists(client, ["parseUAResponse", "ParseUAResponse"], rx)

        aarq_frames = _get_req_frames(client, ["aarqRequest", "AARQRequest"])
        for index, frame in enumerate(aarq_frames):
            tx = _frameify(frame)
            transport.write(tx)
            transport.flush()
            rx = transport.read(1024)
            if rx:
                frames.append({"stage": f"aarq_{index}", "tx_hex": tx.hex(), "rx_hex": rx.hex()})
                _call_if_exists(
                    client,
                    ["parseAareResponse", "parseAAREResponse", "ParseAAREResponse"],
                    rx,
                )

        return (
            True,
            {
                "method": "snrm_then_aarq",
                "client_address": int(config.client_address),
                "server_address": server_address,
            },
            frames,
            client,
        )
    except Exception as exc:  # noqa: BLE001
        frames.append({"stage": "assoc_exception", "error": repr(exc)})
        return False, {"error": "Association failed (SNRM + AARQ)."}, frames, None


def _read_obis_via_gurux(
    transport: SocketSerialAdapter,
    client: Any,
    obis_codes: list[str],
    config: LiveTcpDlmsSessionConfig,
) -> dict[str, str]:
    snapshot_payload: dict[str, str] = {}
    for obis_code in obis_codes:
        value, error = _read_obis_value(transport, client, obis_code, config)
        if error is not None:
            raise RuntimeError(f"OBIS read failed for {obis_code}: {error}")
        snapshot_payload[obis_code] = _coerce_display(value)
    return snapshot_payload


def _read_obis_value(
    transport: SocketSerialAdapter,
    client: Any,
    obis_code: str,
    config: LiveTcpDlmsSessionConfig,
) -> tuple[Any | None, str | None]:
    for _, obj, attr_index in _gurux_strategies_for_ln(obis_code):
        value, error = _gurux_read_attribute(transport, client, obj, attr_index, config)
        if error is None and value is not None:
            return value, None
    return None, "read_failed"


def _gurux_read_attribute(
    transport: SocketSerialAdapter,
    client: Any,
    obj: Any,
    attr_index: int,
    config: LiveTcpDlmsSessionConfig,
) -> tuple[Any | None, str | None]:
    from gurux_dlms.GXByteBuffer import GXByteBuffer
    from gurux_dlms.GXReplyData import GXReplyData

    packets = client.read(obj, attr_index)
    read_buffer = GXByteBuffer()
    reply = GXReplyData()
    for packet in packets:
        read_buffer.clear()
        reply.clear()
        transport.write(bytes(packet))
        transport.flush()
        deadline = time.monotonic() + max(15.0, float(config.dlms_read_timeout_seconds) * 4.0)
        while not reply.isComplete():
            if time.monotonic() > deadline:
                return None, "read_deadline"
            chunk = transport.read(4096)
            if chunk:
                read_buffer.set(chunk)
                client.getData(read_buffer, reply, None)
            else:
                time.sleep(0.05)

    if getattr(reply, "error", None):
        try:
            error_description = str(reply.getError())
        except Exception:  # noqa: BLE001
            error_description = str(reply.error)
        return None, error_description

    try:
        if reply.value is not None:
            client.updateValue(obj, attr_index, reply.value)
    except Exception:  # noqa: BLE001
        pass

    value = getattr(obj, "value", None)
    if value is None and hasattr(obj, "time"):
        value = getattr(obj, "time", None)
    return value, None


def _gurux_strategies_for_ln(logical_name: str) -> list[tuple[str, Any, int]]:
    from gurux_dlms.objects.GXDLMSClock import GXDLMSClock
    from gurux_dlms.objects.GXDLMSData import GXDLMSData
    from gurux_dlms.objects.GXDLMSRegister import GXDLMSRegister

    strategies: list[tuple[str, Any, int]] = []
    if logical_name.startswith("0.0.1."):
        strategies.append(("clock", GXDLMSClock(logical_name), 2))
    if logical_name.startswith("1.0."):
        strategies.append(("register", GXDLMSRegister(logical_name), 2))
    if logical_name.startswith("0.0.96.") or logical_name.startswith("0.0.43."):
        strategies.append(("data", GXDLMSData(logical_name), 2))
    elif not strategies:
        strategies.append(("data", GXDLMSData(logical_name), 2))
    if logical_name.startswith("1.0.") or logical_name.startswith("0.0.1."):
        strategies.append(("data_fallback", GXDLMSData(logical_name), 2))
    return strategies


def _invoke_relay_control_via_gurux(
    transport: SocketSerialAdapter,
    client: Any,
    *,
    relay_obis_code: str,
    operation_name: str,
    config: LiveTcpDlmsSessionConfig,
) -> str:
    from gurux_dlms.objects.GXDLMSDisconnectControl import GXDLMSDisconnectControl

    relay_control = GXDLMSDisconnectControl(relay_obis_code)
    action = _resolve_relay_control_action(relay_control, operation_name)
    reply = _send_pdu_list(transport, client, _frame_list(action(client)), config)
    if reply is None or not reply.isComplete():
        raise RuntimeError(
            f"Relay-control invocation did not complete for '{operation_name}' over live TCP ingress."
        )
    if getattr(reply, "error", 0):
        error_description = _resolve_gurux_reply_error(reply)
        raise RuntimeError(
            f"Relay-control invocation was rejected for '{operation_name}': {error_description}"
        )
    return "acknowledged"


def _read_disconnect_control_state(
    transport: SocketSerialAdapter,
    client: Any,
    *,
    relay_obis_code: str,
    config: LiveTcpDlmsSessionConfig,
) -> LiveTcpRelayControlStateObservation:
    from gurux_dlms.objects.GXDLMSDisconnectControl import GXDLMSDisconnectControl

    relay_control = GXDLMSDisconnectControl(relay_obis_code)
    output_state, output_state_error = _gurux_read_attribute(
        transport,
        client,
        relay_control,
        2,
        config,
    )
    control_state, control_state_error = _gurux_read_attribute(
        transport,
        client,
        relay_control,
        3,
        config,
    )
    return LiveTcpRelayControlStateObservation(
        control_state=_normalize_disconnect_control_state(control_state),
        output_state=_normalize_disconnect_output_state(output_state),
        control_state_error=control_state_error,
        output_state_error=output_state_error,
    )


def _interpret_relay_control_state_transition(
    *,
    operation_name: str,
    before_state: LiveTcpRelayControlStateObservation | None,
    after_state: LiveTcpRelayControlStateObservation | None,
) -> tuple[str, str | None]:
    after_control_state = after_state.control_state if after_state is not None else None
    after_output_state = after_state.output_state if after_state is not None else None
    if operation_name == "remote_disconnect":
        if after_output_state is False or after_control_state in {
            "DISCONNECTED",
            "READY_FOR_RECONNECTION",
        }:
            return "acknowledged", None
    elif operation_name == "remote_reconnect":
        if after_output_state is True or after_control_state == "CONNECTED":
            return "acknowledged", None
    else:
        raise ValueError(f"Unsupported live TCP relay-control operation '{operation_name}'.")

    before_snapshot = before_state.__dict__ if before_state is not None else None
    after_snapshot = after_state.__dict__ if after_state is not None else None
    return (
        "state_mismatch",
        (
            f"Relay-control '{operation_name}' did not reach the expected disconnect-control state. "
            f"Before={before_snapshot}, After={after_snapshot}."
        ),
    )


def _normalize_disconnect_control_state(value: Any) -> str | None:
    if value is None:
        return None
    enum_name = getattr(value, "name", None)
    if isinstance(enum_name, str) and enum_name:
        return enum_name
    if isinstance(value, bool):
        return "CONNECTED" if value else "DISCONNECTED"
    if isinstance(value, int):
        mapping = {
            0: "DISCONNECTED",
            1: "CONNECTED",
            2: "READY_FOR_RECONNECTION",
        }
        return mapping.get(value, str(value))
    normalized = _coerce_display(value).strip().upper().replace(" ", "_")
    if normalized in {"0", "DISCONNECTED"}:
        return "DISCONNECTED"
    if normalized in {"1", "CONNECTED"}:
        return "CONNECTED"
    if normalized in {"2", "READY_FOR_RECONNECTION"}:
        return "READY_FOR_RECONNECTION"
    return normalized or None


def _normalize_disconnect_output_state(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    normalized = _coerce_display(value).strip().lower()
    if normalized in {"true", "1", "connected", "on", "closed"}:
        return True
    if normalized in {"false", "0", "disconnected", "off", "open"}:
        return False
    return None


def _resolve_gurux_reply_error(reply: Any) -> str:
    try:
        error_description = reply.getError()
        if error_description is not None:
            return str(error_description)
    except Exception:  # noqa: BLE001
        pass
    try:
        error_description = reply.getErrorMessage()
        if error_description is not None:
            return str(error_description)
    except Exception:  # noqa: BLE001
        pass
    return str(getattr(reply, "error", "unknown_error"))


def _resolve_relay_control_action(relay_control: Any, operation_name: str) -> Any:
    normalized = operation_name.strip()
    if normalized == "remote_disconnect":
        candidate_names = ["remoteDisconnect", "remote_disconnect"]
    elif normalized == "remote_reconnect":
        candidate_names = ["remoteReconnect", "remote_reconnect"]
    else:
        raise ValueError(f"Unsupported live TCP relay-control operation '{operation_name}'.")

    for name in candidate_names:
        action = getattr(relay_control, name, None)
        if action is not None:
            return action
    raise AttributeError(
        f"Unable to resolve Gurux disconnect-control action for '{operation_name}'."
    )


def _try_gurux_disconnect(
    transport: SocketSerialAdapter,
    client: Any,
    config: LiveTcpDlmsSessionConfig,
) -> None:
    if not config.send_hdlc_disc_before_close:
        return
    try:
        request = client.disconnectRequest()
        if request is None:
            return
        tx = _frameify(request)
        transport.reset_input_buffer()
        transport.write(tx)
        transport.flush()
        time.sleep(0.05)
        previous_timeout = transport.timeout
        try:
            transport.timeout = float(config.disc_drain_timeout_seconds)
            transport.read(4096)
        finally:
            if previous_timeout is not None:
                transport.timeout = previous_timeout
    except Exception as exc:  # noqa: BLE001
        logger.debug("Ignoring HDLC DISC failure on live TCP ingress: %s", exc)


def _hdlc_next_address_raw(ua: bytes, pos: int) -> tuple[bytes, int] | None:
    if pos >= len(ua):
        return None
    start = pos
    while pos < len(ua):
        current = ua[pos]
        pos += 1
        if current & 1:
            return ua[start:pos], pos
    return None


def _parse_ua_hdlc_header_addresses(ua: bytes) -> tuple[bytes, bytes] | None:
    if len(ua) < 14 or ua[0] != 0x7E or ua[-1] != 0x7E:
        return None
    index = 1
    format_byte = ua[index]
    index += 1
    if (format_byte & 0xF0) != 0xA0:
        return None
    if (format_byte & 0x07) != 0:
        _ = (format_byte & 0x07) << 8
    if index >= len(ua):
        return None
    index += 1
    destination = _hdlc_next_address_raw(ua, index)
    if destination is None:
        return None
    destination_raw, next_index = destination
    source = _hdlc_next_address_raw(ua, next_index)
    if source is None:
        return None
    source_raw, _ = source
    if not destination_raw or not source_raw:
        return None
    return source_raw, destination_raw


def _parse_ua_dlms_addresses_sunrise_marker(ua: bytes) -> tuple[bytes, bytes] | None:
    if not ua or ua[0] != 0x7E:
        return None
    marker = bytes.fromhex("00020463")
    marker_index = ua.find(marker)
    if marker_index < 1 or marker_index + 4 > len(ua):
        return None
    return ua[marker_index : marker_index + 4], ua[marker_index - 1 : marker_index]


def _parse_ua_dlms_addresses(ua: bytes) -> tuple[bytes, bytes] | None:
    header_addresses = _parse_ua_hdlc_header_addresses(ua)
    if header_addresses is not None:
        return header_addresses
    return _parse_ua_dlms_addresses_sunrise_marker(ua)


def _client_raw_to_gurux_logical(client_raw: bytes) -> int:
    from gurux_dlms.GXByteBuffer import GXByteBuffer
    from gurux_dlms.internal._GXCommon import _GXCommon

    buffer = GXByteBuffer(client_raw)
    buffer.position = 0
    return int(_GXCommon.getHDLCAddress(buffer))


def _raw_hdlc_server_to_gurux_logical(
    server_raw: bytes,
    *,
    preferred_server_address_size: int,
) -> int:
    from gurux_dlms.GXDLMS import GXDLMS

    try_sizes: list[int] = []
    for size in (preferred_server_address_size, 4, 2, 1):
        if size not in try_sizes and 1 <= size <= 4:
            try_sizes.append(size)

    for size in try_sizes:
        for value in range(0, 0x200000):
            try:
                if bytes(GXDLMS.getAddressBytes(value, size)) == bytes(server_raw):
                    return value
            except Exception:  # noqa: BLE001
                continue

    return int.from_bytes(bytes(server_raw).ljust(4, b"\x00")[:4], "big")


def _extract_ua_information_field(ua: bytes) -> bytes:
    if len(ua) < 12 or ua[0] != 0x7E or ua[-1] != 0x7E:
        return b""
    for index in range(1, len(ua) - 6):
        if ua[index] == 0x81 and ua[index + 1] == 0x80:
            return ua[index : len(ua) - 3]
    return b""


def _read_hdlc_frame(transport: SocketSerialAdapter, *, max_wait: float) -> bytes:
    deadline = time.monotonic() + max_wait
    buffer = bytearray()
    while time.monotonic() < deadline:
        chunk = transport.read(512)
        if chunk:
            buffer.extend(chunk)
            if buffer and buffer[0] == 0x7E and len(buffer) > 1:
                try:
                    end_index = buffer.index(0x7E, 1)
                except ValueError:
                    continue
                return bytes(buffer[: end_index + 1])
        else:
            time.sleep(0.02)
    return bytes(buffer)


def _send_pdu_list(
    transport: SocketSerialAdapter,
    client: Any,
    pdus: list[Any],
    config: LiveTcpDlmsSessionConfig,
) -> Any:
    from gurux_dlms.GXByteBuffer import GXByteBuffer
    from gurux_dlms.GXReplyData import GXReplyData

    deadline = time.monotonic() + max(15.0, float(config.dlms_read_timeout_seconds) * 3.0)
    read_buffer = GXByteBuffer()
    last_reply: Any = GXReplyData()
    for pdu in pdus:
        read_buffer.clear()
        last_reply.clear()
        _exchange_gurux_reply(
            transport,
            client,
            request_pdu=pdu,
            reply=last_reply,
            read_buffer=read_buffer,
            deadline=deadline,
        )
        while last_reply.isMoreData():
            next_pdu = None if last_reply.isStreaming() else client.receiverReady(last_reply)
            _exchange_gurux_reply(
                transport,
                client,
                request_pdu=next_pdu,
                reply=last_reply,
                read_buffer=read_buffer,
                deadline=deadline,
            )
    return last_reply


def _exchange_gurux_reply(
    transport: SocketSerialAdapter,
    client: Any,
    *,
    request_pdu: Any,
    reply: Any,
    read_buffer: Any,
    deadline: float,
) -> None:
    read_buffer.clear()
    if request_pdu is not None:
        transport.write(_frameify(request_pdu))
        transport.flush()
    while not reply.isComplete():
        if time.monotonic() > deadline:
            return
        chunk = transport.read(4096)
        if chunk:
            read_buffer.set(chunk)
            client.getData(read_buffer, reply, None)
        else:
            time.sleep(0.05)


def _get_req_frames(client: Any, candidate_names: list[str]) -> list[Any]:
    for name in candidate_names:
        method = getattr(client, name, None)
        if method is None:
            continue
        frames = method()
        if isinstance(frames, list):
            return frames
        return [frames]
    raise AttributeError(f"Unable to resolve request frame method from {candidate_names!r}.")


def _call_if_exists(client: Any, candidate_names: list[str], *args: object) -> Any | None:
    for name in candidate_names:
        method = getattr(client, name, None)
        if method is None:
            continue
        return method(*args)
    return None


def _frame_list(frames: Any) -> list[Any]:
    if isinstance(frames, list):
        return frames
    return [frames]


def _frameify(frame: Any) -> bytes:
    if isinstance(frame, bytes):
        return frame
    if isinstance(frame, bytearray):
        return bytes(frame)
    if isinstance(frame, list):
        return bytes(frame)
    return bytes(frame)


def _resolve_gurux_authentication(authentication_mode: str) -> Any:
    from gurux_dlms.enums.Authentication import Authentication

    normalized = authentication_mode.strip().lower()
    if normalized == "none":
        return Authentication.NONE
    if normalized == "low":
        return Authentication.LOW
    raise NotImplementedError(
        f"Authentication mode '{authentication_mode}' is not yet supported for live TCP ingress."
    )


def _resolve_gurux_interface_type() -> Any:
    from gurux_dlms.enums.InterfaceType import InterfaceType

    return InterfaceType.HDLC


def _coerce_display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("ascii", errors="replace").rstrip("\x00").strip()
    return str(value).strip()

