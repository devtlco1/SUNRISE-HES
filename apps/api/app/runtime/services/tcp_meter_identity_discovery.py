from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.connectivity.enums import ProtocolFamily
from app.modules.connectivity.models import ProtocolAssociationProfile
from app.runtime.adapters.gurux_tcp_ingress import (
    IDENTITY_DISCOVERY_OBIS_CODES,
    LiveTcpDlmsSessionConfig,
    LiveTcpIdentityDiscoveryExecution,
    execute_identity_discovery_over_tcp_ingress,
)
from app.runtime.services.runtime_secret_refs import resolve_runtime_secret_ref
from app.runtime.services.tcp_meter_ingress import (
    borrow_runtime_tcp_meter_ingress_unbound_connection,
    get_runtime_tcp_meter_ingress_status,
    mark_runtime_tcp_meter_ingress_connection_dead,
)


@dataclass(frozen=True)
class RuntimeTcpMeterIdentityDiscoveryResult:
    success: bool
    active_connection_id: str
    protocol_association_profile_id: UUID
    discovered_identity_value: str | None
    discovered_identity_obis_code: str | None
    identity_values: dict[str, str]
    protocol_path_used: str
    diagnostic_message: str
    remote_addr: str | None
    remote_port: int | None


def discover_runtime_tcp_meter_identity(
    session: Session,
    *,
    protocol_association_profile_id: UUID,
) -> RuntimeTcpMeterIdentityDiscoveryResult:
    status_snapshot = get_runtime_tcp_meter_ingress_status()
    if not status_snapshot.listener_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime TCP meter ingress listener is disabled.",
        )
    if not status_snapshot.connected or status_snapshot.active_connection_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime TCP meter ingress has no active live connection to discover.",
        )
    if status_snapshot.bound_meter_id is not None or status_snapshot.bound_endpoint_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime TCP meter ingress connection is already bound. Discovery is only available before bind.",
        )
    if status_snapshot.connection_in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime TCP meter ingress connection is already in use.",
        )

    profile = session.get(ProtocolAssociationProfile, protocol_association_profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol association profile was not found for live identity discovery.",
        )
    if profile.protocol_family != ProtocolFamily.DLMS_COSEM:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live identity discovery currently supports only DLMS/COSEM protocol profiles.",
        )
    if not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol association profile must be active for live identity discovery.",
        )

    config = _build_live_tcp_discovery_config(profile)
    with borrow_runtime_tcp_meter_ingress_unbound_connection() as borrowed_connection:
        if borrowed_connection is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime TCP meter ingress connection is unavailable for identity discovery.",
            )

        try:
            execution = execute_identity_discovery_over_tcp_ingress(
                sock=borrowed_connection.socket,
                config=config,
            )
        except Exception as exc:
            mark_runtime_tcp_meter_ingress_connection_dead(borrowed_connection.connection_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Live identity discovery failed: {exc}",
            ) from exc

        return _build_discovery_result(
            execution=execution,
            active_connection_id=borrowed_connection.connection_id,
            protocol_association_profile_id=profile.id,
            remote_addr=borrowed_connection.remote_addr,
            remote_port=borrowed_connection.remote_port,
        )


def _build_live_tcp_discovery_config(
    profile: ProtocolAssociationProfile,
) -> LiveTcpDlmsSessionConfig:
    profile_settings = profile.profile_settings or {}
    password = resolve_runtime_secret_ref(profile.password_secret_ref)
    if profile.authentication_mode.value == "low" and password is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live identity discovery requires a resolvable password secret for LOW authentication.",
        )

    def _int_setting(key: str, default: int) -> int:
        return int(profile_settings.get(key, default))

    def _float_setting(key: str, default: float) -> float:
        return float(profile_settings.get(key, default))

    def _bool_setting(key: str, default: bool) -> bool:
        value = profile_settings.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    ack_candidates_raw = profile_settings.get("iec_ack_hex_candidates")
    ack_candidates = (
        [str(item) for item in ack_candidates_raw if str(item).strip()]
        if isinstance(ack_candidates_raw, list)
        else ["063235320D0A", "06B235B28D0A"]
    )

    start_protocol = "iec62056_21" if profile.iec62056_21_enabled else "dlms"
    configured_start_protocol = profile_settings.get("tcp_start_protocol")
    if isinstance(configured_start_protocol, str):
        normalized = configured_start_protocol.strip().lower()
        if normalized in {"iec", "iec62056_21", "iec62056-21"}:
            start_protocol = "iec62056_21"
        elif normalized in {"dlms", "hdlc", "snrm"}:
            start_protocol = "dlms"

    return LiveTcpDlmsSessionConfig(
        start_protocol=start_protocol,  # type: ignore[arg-type]
        client_address=profile.client_address,
        server_address=profile.server_address,
        server_address_size=int(profile_settings.get("server_address_size", 1)),
        authentication_mode=profile.authentication_mode.value,
        password=password,
        iec_ack_hex_candidates=ack_candidates,
        use_broadcast_snrm_first=_bool_setting("use_broadcast_snrm_first", True),
        broadcast_snrm_hex=str(
            profile_settings.get("broadcast_snrm_hex", "7EA00AFEFEFEFF0393C9837E")
        ),
        after_iec_sleep_ms=_int_setting("after_iec_sleep_ms", 1200),
        dlms_read_timeout_seconds=_float_setting("dlms_read_timeout_seconds", 2.5),
        iec_serial_timeout_seconds=_float_setting("iec_serial_timeout_seconds", 5.0),
        iec_wake_zero_bytes=_int_setting("iec_wake_zero_bytes", 0),
        iec_wake_post_delay_ms=_int_setting("iec_wake_post_delay_ms", 0),
        iec_ident_retries=_int_setting("iec_ident_retries", 4),
        iec_ident_retry_delay_ms=_int_setting("iec_ident_retry_delay_ms", 350),
        before_first_iec_send_delay_ms=0,
        ua_swap_addresses=_bool_setting("ua_swap_addresses", False),
        send_hdlc_disc_before_close=_bool_setting("send_hdlc_disc_before_close", True),
        disc_drain_timeout_seconds=_float_setting("disc_drain_timeout_seconds", 0.4),
    )


def _build_discovery_result(
    *,
    execution: LiveTcpIdentityDiscoveryExecution,
    active_connection_id: str,
    protocol_association_profile_id: UUID,
    remote_addr: str | None,
    remote_port: int | None,
) -> RuntimeTcpMeterIdentityDiscoveryResult:
    success = execution.identity_value is not None
    discovered_obis = execution.identity_obis_code
    message = (
        "Live ingress identity discovery completed."
        if success
        else "Live ingress identity discovery completed but no identity value was returned."
    )
    return RuntimeTcpMeterIdentityDiscoveryResult(
        success=success,
        active_connection_id=active_connection_id,
        protocol_association_profile_id=protocol_association_profile_id,
        discovered_identity_value=execution.identity_value,
        discovered_identity_obis_code=discovered_obis,
        identity_values=execution.identity_values,
        protocol_path_used=str(execution.protocol_trace.get("association_method", "unknown")),
        diagnostic_message=(
            f"{message} Identity OBIS candidates: {', '.join(IDENTITY_DISCOVERY_OBIS_CODES)}"
        ),
        remote_addr=remote_addr,
        remote_port=remote_port,
    )

