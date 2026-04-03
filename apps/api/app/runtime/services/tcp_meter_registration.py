from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.connectivity.enums import (
    CommunicationEndpointType,
    ConnectivityTransportType,
    EndpointAssignmentStatus,
)
from app.modules.connectivity.models import CommunicationEndpoint, MeterEndpointAssignment
from app.modules.meters.enums import MeterCategory, MeterLifecycleStatus, PhaseType
from app.modules.meters.models import Meter, MeterManufacturer, MeterModel, MeterStatusHistory
from app.runtime.services.tcp_meter_identity_discovery import (
    RuntimeTcpMeterIdentityDiscoveryResult,
    discover_runtime_tcp_meter_identity,
)

INGRESS_DISCOVERED_MANUFACTURER_CODE = "runtime-ingress-discovered"
INGRESS_DISCOVERED_MANUFACTURER_NAME = "Runtime Ingress Discovered"
INGRESS_DISCOVERED_MODEL_CODE = "runtime-ingress-generic-dlms"
INGRESS_DISCOVERED_MODEL_NAME = "Runtime Ingress Generic DLMS Meter"


@dataclass(frozen=True)
class RuntimeTcpMeterRegistrationResult:
    success: bool
    active_connection_id: str
    protocol_association_profile_id: UUID
    discovered_identity_value: str
    discovered_identity_obis_code: str | None
    matched_existing_meter: bool
    meter_id: UUID
    communication_endpoint_id: UUID
    assignment_id: UUID
    created_meter: bool
    created_endpoint: bool
    created_assignment: bool
    diagnostic_message: str


def persist_runtime_tcp_meter_discovered_identity(
    session: Session,
    *,
    protocol_association_profile_id: UUID,
) -> RuntimeTcpMeterRegistrationResult:
    discovery = discover_runtime_tcp_meter_identity(
        session,
        protocol_association_profile_id=protocol_association_profile_id,
    )
    identity_value = (discovery.discovered_identity_value or "").strip()
    if not discovery.success or not identity_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Live ingress identity discovery did not return a usable unique meter identity "
                "for persistence."
            ),
        )

    meter = _find_meter_by_serial(session, identity_value)
    created_meter = False
    if meter is None:
        meter = _create_discovered_meter(session, discovery=discovery)
        created_meter = True

    endpoint, assignment, created_endpoint, created_assignment = (
        _resolve_or_create_ingress_endpoint_assignment(
            session,
            meter=meter,
            discovery=discovery,
        )
    )
    session.commit()

    return RuntimeTcpMeterRegistrationResult(
        success=True,
        active_connection_id=discovery.active_connection_id,
        protocol_association_profile_id=discovery.protocol_association_profile_id,
        discovered_identity_value=identity_value,
        discovered_identity_obis_code=discovery.discovered_identity_obis_code,
        matched_existing_meter=not created_meter,
        meter_id=meter.id,
        communication_endpoint_id=endpoint.id,
        assignment_id=assignment.id,
        created_meter=created_meter,
        created_endpoint=created_endpoint,
        created_assignment=created_assignment,
        diagnostic_message=_build_registration_message(
            discovery=discovery,
            matched_existing_meter=not created_meter,
            created_meter=created_meter,
            created_endpoint=created_endpoint,
            created_assignment=created_assignment,
        ),
    )


def _find_meter_by_serial(session: Session, serial_number: str) -> Meter | None:
    return session.scalar(
        select(Meter).where(func.lower(Meter.serial_number) == serial_number.strip().lower())
    )


def _create_discovered_meter(
    session: Session,
    *,
    discovery: RuntimeTcpMeterIdentityDiscoveryResult,
) -> Meter:
    manufacturer, meter_model = _resolve_or_create_ingress_placeholder_model(session)
    meter = Meter(
        serial_number=discovery.discovered_identity_value.strip(),
        manufacturer_id=manufacturer.id,
        meter_model_id=meter_model.id,
        current_status=MeterLifecycleStatus.REGISTERED,
        is_active=True,
        notes="Auto-registered from live TCP ingress identity discovery.",
        metadata_json={
            "runtime_ingress": {
                "source": "tcp_meter_identity_discovery",
                "active_connection_id": discovery.active_connection_id,
                "protocol_association_profile_id": str(discovery.protocol_association_profile_id),
                "identity_obis_code": discovery.discovered_identity_obis_code,
                "identity_values": discovery.identity_values,
                "protocol_path_used": discovery.protocol_path_used,
                "remote_addr": discovery.remote_addr,
                "remote_port": discovery.remote_port,
            }
        },
    )
    session.add(meter)
    session.flush()
    session.add(
        MeterStatusHistory(
            meter_id=meter.id,
            previous_status=None,
            new_status=MeterLifecycleStatus.REGISTERED,
            changed_by_user_id=None,
            reason="Auto-registered from live TCP ingress identity discovery.",
        )
    )
    return meter


def _resolve_or_create_ingress_placeholder_model(
    session: Session,
) -> tuple[MeterManufacturer, MeterModel]:
    manufacturer = session.scalar(
        select(MeterManufacturer).where(
            func.lower(MeterManufacturer.code) == INGRESS_DISCOVERED_MANUFACTURER_CODE.lower()
        )
    )
    if manufacturer is None:
        manufacturer = MeterManufacturer(
            name=INGRESS_DISCOVERED_MANUFACTURER_NAME,
            code=INGRESS_DISCOVERED_MANUFACTURER_CODE,
            is_active=True,
        )
        session.add(manufacturer)
        session.flush()

    meter_model = session.scalar(
        select(MeterModel).where(
            MeterModel.manufacturer_id == manufacturer.id,
            func.lower(MeterModel.model_code) == INGRESS_DISCOVERED_MODEL_CODE.lower(),
        )
    )
    if meter_model is None:
        meter_model = MeterModel(
            manufacturer_id=manufacturer.id,
            model_code=INGRESS_DISCOVERED_MODEL_CODE,
            display_name=INGRESS_DISCOVERED_MODEL_NAME,
            phase_type=PhaseType.SINGLE_PHASE,
            meter_category=MeterCategory.ELECTRICITY,
            dlms_capable=True,
            is_active=True,
        )
        session.add(meter_model)
        session.flush()

    return manufacturer, meter_model


def _resolve_or_create_ingress_endpoint_assignment(
    session: Session,
    *,
    meter: Meter,
    discovery: RuntimeTcpMeterIdentityDiscoveryResult,
) -> tuple[CommunicationEndpoint, MeterEndpointAssignment, bool, bool]:
    endpoint_code = _build_ingress_endpoint_code(discovery.discovered_identity_value)

    assignment = session.scalar(
        select(MeterEndpointAssignment)
        .join(CommunicationEndpoint, CommunicationEndpoint.id == MeterEndpointAssignment.endpoint_id)
        .where(
            MeterEndpointAssignment.meter_id == meter.id,
            MeterEndpointAssignment.assignment_status == EndpointAssignmentStatus.ACTIVE,
            MeterEndpointAssignment.unassigned_at.is_(None),
            func.lower(CommunicationEndpoint.code) == endpoint_code.lower(),
            CommunicationEndpoint.is_active.is_(True),
        )
        .order_by(
            MeterEndpointAssignment.is_primary.desc(),
            MeterEndpointAssignment.assigned_at.desc(),
        )
    )
    if assignment is not None:
        endpoint = session.get(CommunicationEndpoint, assignment.endpoint_id)
        if endpoint is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ingress registration found a stale endpoint assignment reference.",
            )
        return endpoint, assignment, False, False

    endpoint = session.scalar(
        select(CommunicationEndpoint).where(func.lower(CommunicationEndpoint.code) == endpoint_code.lower())
    )
    created_endpoint = False
    if endpoint is None:
        host = discovery.remote_addr
        port = discovery.remote_port
        if not host or port is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Live ingress registration cannot create a TCP endpoint because the active "
                    "connection remote host and port are unavailable."
                ),
            )
        endpoint = CommunicationEndpoint(
            code=endpoint_code,
            display_name=_truncate(f"TCP Ingress {discovery.discovered_identity_value}", 255),
            endpoint_type=CommunicationEndpointType.TCP,
            transport_type=ConnectivityTransportType.TCP_IP,
            host=host,
            port=port,
            gateway_identifier="runtime_tcp_meter_ingress",
            is_active=True,
            notes=(
                "Auto-created for live TCP ingress discovery. Stored host/port reflect the "
                "observed ingress session and may require operator review before non-live use."
            ),
        )
        session.add(endpoint)
        session.flush()
        created_endpoint = True

    conflicting_assignment = session.scalar(
        select(MeterEndpointAssignment).where(
            MeterEndpointAssignment.endpoint_id == endpoint.id,
            MeterEndpointAssignment.meter_id != meter.id,
            MeterEndpointAssignment.assignment_status == EndpointAssignmentStatus.ACTIVE,
            MeterEndpointAssignment.unassigned_at.is_(None),
        )
    )
    if conflicting_assignment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The discovered ingress endpoint is already assigned to a different meter.",
        )

    has_active_primary = session.scalar(
        select(MeterEndpointAssignment.id).where(
            MeterEndpointAssignment.meter_id == meter.id,
            MeterEndpointAssignment.assignment_status == EndpointAssignmentStatus.ACTIVE,
            MeterEndpointAssignment.unassigned_at.is_(None),
            MeterEndpointAssignment.is_primary.is_(True),
        )
    )
    assignment = MeterEndpointAssignment(
        meter_id=meter.id,
        endpoint_id=endpoint.id,
        is_primary=has_active_primary is None,
        assignment_status=EndpointAssignmentStatus.ACTIVE,
        notes="Auto-created for live TCP ingress discovery persistence.",
    )
    session.add(assignment)
    session.flush()
    return endpoint, assignment, created_endpoint, True


def _build_registration_message(
    *,
    discovery: RuntimeTcpMeterIdentityDiscoveryResult,
    matched_existing_meter: bool,
    created_meter: bool,
    created_endpoint: bool,
    created_assignment: bool,
) -> str:
    actions: list[str] = []
    if matched_existing_meter:
        actions.append("matched existing meter")
    if created_meter:
        actions.append("created meter")
    if created_endpoint:
        actions.append("created ingress endpoint")
    if created_assignment:
        actions.append("created endpoint assignment")
    action_summary = ", ".join(actions) if actions else "reused existing meter registration artifacts"
    return (
        "Live ingress discovery persistence completed: "
        f"{action_summary}. Identity {discovery.discovered_identity_value!r} from "
        f"{discovery.discovered_identity_obis_code or 'unknown OBIS'} remains available for manual bind."
    )


def _build_ingress_endpoint_code(identity_value: str) -> str:
    normalized = _normalize_code_fragment(identity_value)
    digest = hashlib.sha1(identity_value.encode("utf-8")).hexdigest()[:10]
    return _truncate(f"tcp-ingress-{normalized}-{digest}", 64)


def _normalize_code_fragment(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "meter"


def _truncate(value: str, max_length: int) -> str:
    return value[:max_length]
