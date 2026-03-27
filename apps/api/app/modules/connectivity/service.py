from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.connectivity.models import (
    CommunicationEndpoint,
    ConnectivityCredential,
    ConnectivitySessionHistory,
    MeterEndpointAssignment,
    ProtocolAssociationProfile,
)
from app.modules.connectivity.schemas import (
    CommunicationEndpointCreate,
    CommunicationEndpointListResponse,
    CommunicationEndpointResponse,
    CommunicationEndpointUpdate,
    ConnectivityCredentialCreate,
    ConnectivityCredentialListResponse,
    ConnectivityCredentialResponse,
    ConnectivityCredentialUpdate,
    ConnectivitySessionHistoryListResponse,
    ConnectivitySessionHistoryResponse,
    MeterEndpointAssignmentCreate,
    MeterEndpointAssignmentListResponse,
    MeterEndpointAssignmentResponse,
    ProtocolAssociationProfileCreate,
    ProtocolAssociationProfileListResponse,
    ProtocolAssociationProfileResponse,
    ProtocolAssociationProfileUpdate,
)
from app.modules.meters.models import Meter


def list_communication_endpoints(session: Session) -> CommunicationEndpointListResponse:
    total = session.scalar(select(func.count()).select_from(CommunicationEndpoint)) or 0
    items = session.scalars(
        select(CommunicationEndpoint).order_by(CommunicationEndpoint.display_name.asc())
    ).all()
    return CommunicationEndpointListResponse(
        total=total,
        items=[serialize_communication_endpoint(item) for item in items],
    )


def get_communication_endpoint(session: Session, endpoint_id: uuid.UUID) -> CommunicationEndpoint:
    endpoint = session.get(CommunicationEndpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication endpoint not found.")
    return endpoint


def create_communication_endpoint(
    session: Session,
    payload: CommunicationEndpointCreate,
) -> CommunicationEndpoint:
    existing = session.scalar(
        select(CommunicationEndpoint).where(func.lower(CommunicationEndpoint.code) == payload.code.lower())
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Communication endpoint code already exists.")

    endpoint = CommunicationEndpoint(**payload.model_dump())
    endpoint.code = endpoint.code.strip().lower()
    endpoint.display_name = endpoint.display_name.strip()
    _validate_endpoint_transport_consistency(endpoint)
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)
    return endpoint


def update_communication_endpoint(
    session: Session,
    *,
    endpoint_id: uuid.UUID,
    payload: CommunicationEndpointUpdate,
) -> CommunicationEndpoint:
    endpoint = get_communication_endpoint(session, endpoint_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(endpoint, field, value)
    _validate_endpoint_transport_consistency(endpoint)
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)
    return endpoint


def list_protocol_association_profiles(session: Session) -> ProtocolAssociationProfileListResponse:
    total = session.scalar(select(func.count()).select_from(ProtocolAssociationProfile)) or 0
    items = session.scalars(
        select(ProtocolAssociationProfile).order_by(ProtocolAssociationProfile.name.asc())
    ).all()
    return ProtocolAssociationProfileListResponse(
        total=total,
        items=[serialize_protocol_association_profile(item) for item in items],
    )


def get_protocol_association_profile(
    session: Session,
    profile_id: uuid.UUID,
) -> ProtocolAssociationProfile:
    profile = session.get(ProtocolAssociationProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol association profile not found.")
    return profile


def create_protocol_association_profile(
    session: Session,
    payload: ProtocolAssociationProfileCreate,
) -> ProtocolAssociationProfile:
    existing = session.scalar(
        select(ProtocolAssociationProfile).where(
            func.lower(ProtocolAssociationProfile.code) == payload.code.lower()
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol association profile code already exists.",
        )

    profile = ProtocolAssociationProfile(**payload.model_dump())
    profile.code = profile.code.strip().lower()
    profile.name = profile.name.strip()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_protocol_association_profile(
    session: Session,
    *,
    profile_id: uuid.UUID,
    payload: ProtocolAssociationProfileUpdate,
) -> ProtocolAssociationProfile:
    profile = get_protocol_association_profile(session, profile_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def list_connectivity_credentials(session: Session) -> ConnectivityCredentialListResponse:
    total = session.scalar(select(func.count()).select_from(ConnectivityCredential)) or 0
    items = session.scalars(select(ConnectivityCredential).order_by(ConnectivityCredential.code.asc())).all()
    return ConnectivityCredentialListResponse(
        total=total,
        items=[serialize_connectivity_credential(item) for item in items],
    )


def get_connectivity_credential(session: Session, credential_id: uuid.UUID) -> ConnectivityCredential:
    credential = session.get(ConnectivityCredential, credential_id)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connectivity credential not found.")
    return credential


def create_connectivity_credential(
    session: Session,
    payload: ConnectivityCredentialCreate,
) -> ConnectivityCredential:
    existing = session.scalar(
        select(ConnectivityCredential).where(func.lower(ConnectivityCredential.code) == payload.code.lower())
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connectivity credential code already exists.")

    credential = ConnectivityCredential(**payload.model_dump())
    credential.code = credential.code.strip().lower()
    session.add(credential)
    session.commit()
    session.refresh(credential)
    return credential


def update_connectivity_credential(
    session: Session,
    *,
    credential_id: uuid.UUID,
    payload: ConnectivityCredentialUpdate,
) -> ConnectivityCredential:
    credential = get_connectivity_credential(session, credential_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(credential, field, value)
    session.add(credential)
    session.commit()
    session.refresh(credential)
    return credential


def assign_endpoint_to_meter(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: MeterEndpointAssignmentCreate,
) -> MeterEndpointAssignment:
    meter = session.get(Meter, meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")

    endpoint = get_communication_endpoint(session, payload.endpoint_id)

    if payload.is_primary and payload.assignment_status.value == "active":
        existing_primary = session.scalar(
            select(MeterEndpointAssignment).where(
                MeterEndpointAssignment.meter_id == meter_id,
                MeterEndpointAssignment.assignment_status == "active",
                MeterEndpointAssignment.is_primary.is_(True),
                MeterEndpointAssignment.unassigned_at.is_(None),
            )
        )
        if existing_primary is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Meter already has an active primary endpoint assignment.",
            )

    assignment = MeterEndpointAssignment(
        meter_id=meter_id,
        endpoint_id=endpoint.id,
        is_primary=payload.is_primary,
        assignment_status=payload.assignment_status,
        notes=payload.notes,
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return get_meter_endpoint_assignment(session, assignment.id)


def get_meter_endpoint_assignment(
    session: Session,
    assignment_id: uuid.UUID,
) -> MeterEndpointAssignment:
    assignment = session.scalar(
        select(MeterEndpointAssignment)
        .options(selectinload(MeterEndpointAssignment.endpoint))
        .where(MeterEndpointAssignment.id == assignment_id)
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter endpoint assignment not found.")
    return assignment


def list_meter_endpoint_assignments(
    session: Session,
    *,
    meter_id: uuid.UUID,
) -> MeterEndpointAssignmentListResponse:
    total = session.scalar(
        select(func.count()).select_from(MeterEndpointAssignment).where(MeterEndpointAssignment.meter_id == meter_id)
    ) or 0
    items = session.scalars(
        select(MeterEndpointAssignment)
        .options(selectinload(MeterEndpointAssignment.endpoint))
        .where(MeterEndpointAssignment.meter_id == meter_id)
        .order_by(MeterEndpointAssignment.assigned_at.desc())
    ).all()
    return MeterEndpointAssignmentListResponse(
        total=total,
        items=[serialize_meter_endpoint_assignment(item) for item in items],
    )


def list_meter_session_history(
    session: Session,
    *,
    meter_id: uuid.UUID,
    limit: int = 50,
) -> ConnectivitySessionHistoryListResponse:
    total = session.scalar(
        select(func.count()).select_from(ConnectivitySessionHistory).where(
            ConnectivitySessionHistory.meter_id == meter_id
        )
    ) or 0
    items = session.scalars(
        select(ConnectivitySessionHistory)
        .where(ConnectivitySessionHistory.meter_id == meter_id)
        .order_by(ConnectivitySessionHistory.started_at.desc())
        .limit(limit)
    ).all()
    return ConnectivitySessionHistoryListResponse(
        total=total,
        items=[serialize_connectivity_session(item) for item in items],
    )


def list_endpoint_session_history(
    session: Session,
    *,
    endpoint_id: uuid.UUID,
    limit: int = 50,
) -> ConnectivitySessionHistoryListResponse:
    total = session.scalar(
        select(func.count()).select_from(ConnectivitySessionHistory).where(
            ConnectivitySessionHistory.endpoint_id == endpoint_id
        )
    ) or 0
    items = session.scalars(
        select(ConnectivitySessionHistory)
        .where(ConnectivitySessionHistory.endpoint_id == endpoint_id)
        .order_by(ConnectivitySessionHistory.started_at.desc())
        .limit(limit)
    ).all()
    return ConnectivitySessionHistoryListResponse(
        total=total,
        items=[serialize_connectivity_session(item) for item in items],
    )


def serialize_communication_endpoint(item: CommunicationEndpoint) -> CommunicationEndpointResponse:
    return CommunicationEndpointResponse(
        id=item.id,
        code=item.code,
        display_name=item.display_name,
        endpoint_type=item.endpoint_type,
        transport_type=item.transport_type,
        host=item.host,
        port=item.port,
        serial_port_name=item.serial_port_name,
        baud_rate=item.baud_rate,
        parity=item.parity,
        data_bits=item.data_bits,
        stop_bits=item.stop_bits,
        sim_iccid=item.sim_iccid,
        sim_msisdn=item.sim_msisdn,
        imei=item.imei,
        ip_address=str(item.ip_address) if item.ip_address is not None else None,
        apn=item.apn,
        network_provider=item.network_provider,
        gateway_identifier=item.gateway_identifier,
        is_active=item.is_active,
        notes=item.notes,
    )


def serialize_protocol_association_profile(
    item: ProtocolAssociationProfile,
) -> ProtocolAssociationProfileResponse:
    return ProtocolAssociationProfileResponse.model_validate(item, from_attributes=True)


def serialize_connectivity_credential(item: ConnectivityCredential) -> ConnectivityCredentialResponse:
    return ConnectivityCredentialResponse.model_validate(item, from_attributes=True)


def serialize_meter_endpoint_assignment(item: MeterEndpointAssignment) -> MeterEndpointAssignmentResponse:
    return MeterEndpointAssignmentResponse(
        id=item.id,
        meter_id=item.meter_id,
        endpoint_id=item.endpoint_id,
        endpoint_code=item.endpoint.code,
        endpoint_display_name=item.endpoint.display_name,
        assigned_at=item.assigned_at,
        unassigned_at=item.unassigned_at,
        is_primary=item.is_primary,
        assignment_status=item.assignment_status,
        notes=item.notes,
    )


def serialize_connectivity_session(item: ConnectivitySessionHistory) -> ConnectivitySessionHistoryResponse:
    return ConnectivitySessionHistoryResponse(
        id=item.id,
        meter_id=item.meter_id,
        endpoint_id=item.endpoint_id,
        protocol_association_profile_id=item.protocol_association_profile_id,
        started_at=item.started_at,
        ended_at=item.ended_at,
        status=item.status,
        session_purpose=item.session_purpose,
        request_id=item.request_id,
        correlation_id=item.correlation_id,
        error_code=item.error_code,
        error_message=item.error_message,
        bytes_sent=item.bytes_sent,
        bytes_received=item.bytes_received,
        transport_latency_ms=item.transport_latency_ms,
        handshake_stage=item.handshake_stage,
        metadata=item.metadata_json,
    )


def _validate_endpoint_transport_consistency(endpoint: CommunicationEndpoint) -> None:
    if endpoint.endpoint_type.value == "tcp":
        if not endpoint.host or endpoint.port is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TCP endpoints require host and port.",
            )
    if endpoint.endpoint_type.value == "serial":
        if not endpoint.serial_port_name or endpoint.baud_rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Serial endpoints require serial_port_name and baud_rate.",
            )
    if endpoint.endpoint_type.value == "modem":
        if not endpoint.sim_iccid and not endpoint.imei:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Modem endpoints require SIM or modem identity information.",
            )
