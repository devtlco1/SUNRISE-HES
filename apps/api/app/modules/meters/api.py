import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.service import record_audit_event
from app.modules.auth.dependencies import require_permission
from app.modules.consumers.schemas import MeterConsumerLinkageResponse
from app.modules.consumers.service import get_current_consumer_linkage_for_meter
from app.modules.meters.schemas import (
    CommunicationProfileCreate,
    CommunicationProfileListResponse,
    CommunicationProfileResponse,
    MeterCreate,
    MeterDetailResponse,
    MeterFirmwareVersionCreate,
    MeterFirmwareVersionListResponse,
    MeterFirmwareVersionResponse,
    MeterListResponse,
    MeterManufacturerCreate,
    MeterManufacturerListResponse,
    MeterManufacturerResponse,
    MeterModelCreate,
    MeterModelListResponse,
    MeterModelResponse,
    MeterProfileCreate,
    MeterProfileListResponse,
    MeterProfileResponse,
    MeterResponse,
    MeterStatusChangeRequest,
    MeterUpdate,
)
from app.modules.meters.service import (
    create_communication_profile,
    create_firmware_version,
    create_manufacturer,
    create_meter,
    create_meter_model,
    create_meter_profile,
    get_meter_by_id,
    list_communication_profiles,
    list_firmware_versions,
    list_manufacturers,
    list_meter_models,
    list_meter_profiles,
    list_meters,
    serialize_communication_profile,
    serialize_firmware_version,
    serialize_manufacturer,
    serialize_meter,
    serialize_meter_detail,
    serialize_meter_model,
    serialize_meter_profile,
    update_meter,
    change_meter_status,
)
from app.modules.users.models import User

manufacturers_router = APIRouter(prefix="/manufacturers", tags=["manufacturers"])
meter_models_router = APIRouter(prefix="/models", tags=["meter-models"])
firmware_versions_router = APIRouter(prefix="/firmware-versions", tags=["firmware-versions"])
communication_profiles_router = APIRouter(prefix="/communication-profiles", tags=["communication-profiles"])
meter_profiles_router = APIRouter(prefix="/meter-profiles", tags=["meter-profiles"])
meters_router = APIRouter(prefix="/meters", tags=["meters"])


@manufacturers_router.get("", response_model=MeterManufacturerListResponse)
def list_manufacturers_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("device_catalog.read")),
) -> MeterManufacturerListResponse:
    return list_manufacturers(session)


@manufacturers_router.post("", response_model=MeterManufacturerResponse, status_code=status.HTTP_201_CREATED)
def create_manufacturer_endpoint(
    payload: MeterManufacturerCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("device_catalog.write")),
) -> MeterManufacturerResponse:
    manufacturer = create_manufacturer(session, payload)
    response = serialize_manufacturer(manufacturer)
    record_audit_event(
        session,
        action="device_catalog.manufacturers.create",
        resource_type="meter_manufacturers",
        resource_id=manufacturer.id,
        actor_user_id=current_user.id,
        description="Meter manufacturer created.",
        details={"code": manufacturer.code, "name": manufacturer.name},
        request_context=request.state.request_audit_context,
    )
    return response


@meter_models_router.get("", response_model=MeterModelListResponse)
def list_meter_models_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("device_catalog.read")),
) -> MeterModelListResponse:
    return list_meter_models(session)


@meter_models_router.post("", response_model=MeterModelResponse, status_code=status.HTTP_201_CREATED)
def create_meter_model_endpoint(
    payload: MeterModelCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("device_catalog.write")),
) -> MeterModelResponse:
    meter_model = create_meter_model(session, payload)
    response = serialize_meter_model(meter_model)
    record_audit_event(
        session,
        action="device_catalog.models.create",
        resource_type="meter_models",
        resource_id=meter_model.id,
        actor_user_id=current_user.id,
        description="Meter model created.",
        details={"model_code": meter_model.model_code, "manufacturer_id": str(meter_model.manufacturer_id)},
        request_context=request.state.request_audit_context,
    )
    return response


@firmware_versions_router.get("", response_model=MeterFirmwareVersionListResponse)
def list_firmware_versions_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("device_catalog.read")),
) -> MeterFirmwareVersionListResponse:
    return list_firmware_versions(session)


@firmware_versions_router.post("", response_model=MeterFirmwareVersionResponse, status_code=status.HTTP_201_CREATED)
def create_firmware_version_endpoint(
    payload: MeterFirmwareVersionCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("device_catalog.write")),
) -> MeterFirmwareVersionResponse:
    firmware_version = create_firmware_version(session, payload)
    response = serialize_firmware_version(firmware_version)
    record_audit_event(
        session,
        action="device_catalog.firmware_versions.create",
        resource_type="meter_firmware_versions",
        resource_id=firmware_version.id,
        actor_user_id=current_user.id,
        description="Meter firmware version created.",
        details={"version": firmware_version.version, "meter_model_id": str(firmware_version.meter_model_id)},
        request_context=request.state.request_audit_context,
    )
    return response


@communication_profiles_router.get("", response_model=CommunicationProfileListResponse)
def list_communication_profiles_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("device_catalog.read")),
) -> CommunicationProfileListResponse:
    return list_communication_profiles(session)


@communication_profiles_router.post(
    "",
    response_model=CommunicationProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_communication_profile_endpoint(
    payload: CommunicationProfileCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("device_catalog.write")),
) -> CommunicationProfileResponse:
    communication_profile = create_communication_profile(session, payload)
    response = serialize_communication_profile(communication_profile)
    record_audit_event(
        session,
        action="device_catalog.communication_profiles.create",
        resource_type="communication_profiles",
        resource_id=communication_profile.id,
        actor_user_id=current_user.id,
        description="Communication profile created.",
        details={"code": communication_profile.code, "transport_type": communication_profile.transport_type.value},
        request_context=request.state.request_audit_context,
    )
    return response


@meter_profiles_router.get("", response_model=MeterProfileListResponse)
def list_meter_profiles_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("device_catalog.read")),
) -> MeterProfileListResponse:
    return list_meter_profiles(session)


@meter_profiles_router.post("", response_model=MeterProfileResponse, status_code=status.HTTP_201_CREATED)
def create_meter_profile_endpoint(
    payload: MeterProfileCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("device_catalog.write")),
) -> MeterProfileResponse:
    meter_profile = create_meter_profile(session, payload)
    response = serialize_meter_profile(meter_profile)
    record_audit_event(
        session,
        action="device_catalog.meter_profiles.create",
        resource_type="meter_profiles",
        resource_id=meter_profile.id,
        actor_user_id=current_user.id,
        description="Meter profile created.",
        details={"code": meter_profile.code, "meter_model_id": str(meter_profile.meter_model_id)},
        request_context=request.state.request_audit_context,
    )
    return response


@meters_router.get("", response_model=MeterListResponse)
def list_meters_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("meters.read")),
) -> MeterListResponse:
    return list_meters(session, offset=offset, limit=limit, search=search)


@meters_router.post("", response_model=MeterResponse, status_code=status.HTTP_201_CREATED)
def create_meter_endpoint(
    payload: MeterCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("meters.write")),
) -> MeterResponse:
    meter = create_meter(session, payload, changed_by_user_id=current_user.id)
    response = serialize_meter(meter)
    record_audit_event(
        session,
        action="meters.create",
        resource_type="meters",
        resource_id=meter.id,
        actor_user_id=current_user.id,
        description="Meter created.",
        details={"serial_number": meter.serial_number, "current_status": meter.current_status.value},
        request_context=request.state.request_audit_context,
    )
    return response


@meters_router.get("/{meter_id}", response_model=MeterDetailResponse)
def get_meter_endpoint(
    meter_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("meters.read")),
) -> MeterDetailResponse:
    meter = get_meter_by_id(session, meter_id)
    return serialize_meter_detail(meter)


@meters_router.get("/{meter_id}/consumer-linkage", response_model=MeterConsumerLinkageResponse)
def get_meter_consumer_linkage_endpoint(
    meter_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("consumers.read")),
) -> MeterConsumerLinkageResponse:
    return get_current_consumer_linkage_for_meter(session, meter_id=meter_id)


@meters_router.patch("/{meter_id}", response_model=MeterResponse)
def update_meter_endpoint(
    meter_id: uuid.UUID,
    payload: MeterUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("meters.write")),
) -> MeterResponse:
    meter = update_meter(session, meter_id=meter_id, payload=payload)
    response = serialize_meter(meter)
    record_audit_event(
        session,
        action="meters.update",
        resource_type="meters",
        resource_id=meter.id,
        actor_user_id=current_user.id,
        description="Meter updated.",
        details=payload.model_dump(exclude_unset=True),
        request_context=request.state.request_audit_context,
    )
    return response


@meters_router.post("/{meter_id}/status", response_model=MeterDetailResponse)
def change_meter_status_endpoint(
    meter_id: uuid.UUID,
    payload: MeterStatusChangeRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("meters.status.write")),
) -> MeterDetailResponse:
    meter = change_meter_status(
        session,
        meter_id=meter_id,
        payload=payload,
        changed_by_user_id=current_user.id,
    )
    response = serialize_meter_detail(meter)
    record_audit_event(
        session,
        action="meters.status.change",
        resource_type="meters",
        resource_id=meter.id,
        actor_user_id=current_user.id,
        description="Meter status changed.",
        details={"new_status": payload.new_status.value, "reason": payload.reason},
        request_context=request.state.request_audit_context,
    )
    return response
