import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.service import record_audit_event
from app.modules.auth.dependencies import require_permission
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
    MeterEndpointAssignmentCreate,
    MeterEndpointAssignmentListResponse,
    MeterEndpointAssignmentResponse,
    ProtocolAssociationProfileCreate,
    ProtocolAssociationProfileListResponse,
    ProtocolAssociationProfileResponse,
    ProtocolAssociationProfileUpdate,
)
from app.modules.connectivity.service import (
    assign_endpoint_to_meter,
    create_communication_endpoint,
    create_connectivity_credential,
    create_protocol_association_profile,
    get_communication_endpoint,
    get_connectivity_credential,
    get_protocol_association_profile,
    list_communication_endpoints,
    list_connectivity_credentials,
    list_endpoint_session_history,
    list_meter_endpoint_assignments,
    list_meter_session_history,
    list_protocol_association_profiles,
    serialize_communication_endpoint,
    serialize_connectivity_credential,
    serialize_meter_endpoint_assignment,
    serialize_protocol_association_profile,
    update_communication_endpoint,
    update_connectivity_credential,
    update_protocol_association_profile,
)
from app.modules.users.models import User

communication_endpoints_router = APIRouter(prefix="/communication-endpoints", tags=["communication-endpoints"])
protocol_association_profiles_router = APIRouter(
    prefix="/protocol-association-profiles",
    tags=["protocol-association-profiles"],
)
connectivity_credentials_router = APIRouter(prefix="/connectivity-credentials", tags=["connectivity-credentials"])
meter_connectivity_router = APIRouter(prefix="/meters", tags=["meter-connectivity"])


@communication_endpoints_router.get("", response_model=CommunicationEndpointListResponse)
def list_communication_endpoints_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.read")),
) -> CommunicationEndpointListResponse:
    return list_communication_endpoints(session)


@communication_endpoints_router.post("", response_model=CommunicationEndpointResponse, status_code=status.HTTP_201_CREATED)
def create_communication_endpoint_endpoint(
    payload: CommunicationEndpointCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("connectivity.write")),
) -> CommunicationEndpointResponse:
    endpoint = create_communication_endpoint(session, payload)
    response = serialize_communication_endpoint(endpoint)
    record_audit_event(
        session,
        action="connectivity.endpoints.create",
        resource_type="communication_endpoints",
        resource_id=endpoint.id,
        actor_user_id=current_user.id,
        description="Communication endpoint created.",
        details={"code": endpoint.code, "endpoint_type": endpoint.endpoint_type.value},
        request_context=request.state.request_audit_context,
    )
    return response


@communication_endpoints_router.get("/{endpoint_id}", response_model=CommunicationEndpointResponse)
def get_communication_endpoint_endpoint(
    endpoint_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.read")),
) -> CommunicationEndpointResponse:
    endpoint = get_communication_endpoint(session, endpoint_id)
    return serialize_communication_endpoint(endpoint)


@communication_endpoints_router.patch("/{endpoint_id}", response_model=CommunicationEndpointResponse)
def update_communication_endpoint_endpoint(
    endpoint_id: uuid.UUID,
    payload: CommunicationEndpointUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("connectivity.write")),
) -> CommunicationEndpointResponse:
    endpoint = update_communication_endpoint(session, endpoint_id=endpoint_id, payload=payload)
    response = serialize_communication_endpoint(endpoint)
    record_audit_event(
        session,
        action="connectivity.endpoints.update",
        resource_type="communication_endpoints",
        resource_id=endpoint.id,
        actor_user_id=current_user.id,
        description="Communication endpoint updated.",
        details=payload.model_dump(exclude_unset=True),
        request_context=request.state.request_audit_context,
    )
    return response


@communication_endpoints_router.get("/{endpoint_id}/sessions", response_model=ConnectivitySessionHistoryListResponse)
def list_endpoint_sessions_endpoint(
    endpoint_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.sessions.read")),
) -> ConnectivitySessionHistoryListResponse:
    return list_endpoint_session_history(session, endpoint_id=endpoint_id, limit=limit)


@protocol_association_profiles_router.get("", response_model=ProtocolAssociationProfileListResponse)
def list_protocol_association_profiles_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.read")),
) -> ProtocolAssociationProfileListResponse:
    return list_protocol_association_profiles(session)


@protocol_association_profiles_router.post(
    "",
    response_model=ProtocolAssociationProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_protocol_association_profile_endpoint(
    payload: ProtocolAssociationProfileCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("connectivity.write")),
) -> ProtocolAssociationProfileResponse:
    profile = create_protocol_association_profile(session, payload)
    response = serialize_protocol_association_profile(profile)
    record_audit_event(
        session,
        action="connectivity.protocol_profiles.create",
        resource_type="protocol_association_profiles",
        resource_id=profile.id,
        actor_user_id=current_user.id,
        description="Protocol association profile created.",
        details={"code": profile.code, "protocol_family": profile.protocol_family.value},
        request_context=request.state.request_audit_context,
    )
    return response


@protocol_association_profiles_router.get("/{profile_id}", response_model=ProtocolAssociationProfileResponse)
def get_protocol_association_profile_endpoint(
    profile_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.read")),
) -> ProtocolAssociationProfileResponse:
    profile = get_protocol_association_profile(session, profile_id)
    return serialize_protocol_association_profile(profile)


@protocol_association_profiles_router.patch("/{profile_id}", response_model=ProtocolAssociationProfileResponse)
def update_protocol_association_profile_endpoint(
    profile_id: uuid.UUID,
    payload: ProtocolAssociationProfileUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("connectivity.write")),
) -> ProtocolAssociationProfileResponse:
    profile = update_protocol_association_profile(session, profile_id=profile_id, payload=payload)
    response = serialize_protocol_association_profile(profile)
    record_audit_event(
        session,
        action="connectivity.protocol_profiles.update",
        resource_type="protocol_association_profiles",
        resource_id=profile.id,
        actor_user_id=current_user.id,
        description="Protocol association profile updated.",
        details=payload.model_dump(exclude_unset=True),
        request_context=request.state.request_audit_context,
    )
    return response


@connectivity_credentials_router.get("", response_model=ConnectivityCredentialListResponse)
def list_connectivity_credentials_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.credentials.read")),
) -> ConnectivityCredentialListResponse:
    return list_connectivity_credentials(session)


@connectivity_credentials_router.post(
    "",
    response_model=ConnectivityCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_connectivity_credential_endpoint(
    payload: ConnectivityCredentialCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("connectivity.credentials.write")),
) -> ConnectivityCredentialResponse:
    credential = create_connectivity_credential(session, payload)
    response = serialize_connectivity_credential(credential)
    record_audit_event(
        session,
        action="connectivity.credentials.create",
        resource_type="connectivity_credentials",
        resource_id=credential.id,
        actor_user_id=current_user.id,
        description="Connectivity credential created.",
        details={"code": credential.code, "credential_type": credential.credential_type.value},
        request_context=request.state.request_audit_context,
    )
    return response


@connectivity_credentials_router.get("/{credential_id}", response_model=ConnectivityCredentialResponse)
def get_connectivity_credential_endpoint(
    credential_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.credentials.read")),
) -> ConnectivityCredentialResponse:
    credential = get_connectivity_credential(session, credential_id)
    return serialize_connectivity_credential(credential)


@connectivity_credentials_router.patch("/{credential_id}", response_model=ConnectivityCredentialResponse)
def update_connectivity_credential_endpoint(
    credential_id: uuid.UUID,
    payload: ConnectivityCredentialUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("connectivity.credentials.write")),
) -> ConnectivityCredentialResponse:
    credential = update_connectivity_credential(session, credential_id=credential_id, payload=payload)
    response = serialize_connectivity_credential(credential)
    record_audit_event(
        session,
        action="connectivity.credentials.update",
        resource_type="connectivity_credentials",
        resource_id=credential.id,
        actor_user_id=current_user.id,
        description="Connectivity credential updated.",
        details=payload.model_dump(exclude_unset=True),
        request_context=request.state.request_audit_context,
    )
    return response


@meter_connectivity_router.post(
    "/{meter_id}/endpoint-assignments",
    response_model=MeterEndpointAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_meter_endpoint_endpoint(
    meter_id: uuid.UUID,
    payload: MeterEndpointAssignmentCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("connectivity.assign.write")),
) -> MeterEndpointAssignmentResponse:
    assignment = assign_endpoint_to_meter(session, meter_id=meter_id, payload=payload)
    response = serialize_meter_endpoint_assignment(assignment)
    record_audit_event(
        session,
        action="connectivity.assignments.create",
        resource_type="meter_endpoint_assignments",
        resource_id=assignment.id,
        actor_user_id=current_user.id,
        description="Communication endpoint assigned to meter.",
        details={
            "meter_id": str(meter_id),
            "endpoint_id": str(assignment.endpoint_id),
            "is_primary": assignment.is_primary,
        },
        request_context=request.state.request_audit_context,
    )
    return response


@meter_connectivity_router.get(
    "/{meter_id}/endpoint-assignments",
    response_model=MeterEndpointAssignmentListResponse,
)
def list_meter_assignments_endpoint(
    meter_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.read")),
) -> MeterEndpointAssignmentListResponse:
    return list_meter_endpoint_assignments(session, meter_id=meter_id)


@meter_connectivity_router.get(
    "/{meter_id}/sessions",
    response_model=ConnectivitySessionHistoryListResponse,
)
def list_meter_sessions_endpoint(
    meter_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("connectivity.sessions.read")),
) -> ConnectivitySessionHistoryListResponse:
    return list_meter_session_history(session, meter_id=meter_id, limit=limit)
