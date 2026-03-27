from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.meters.models import (
    CommunicationProfile,
    Meter,
    MeterFirmwareVersion,
    MeterManufacturer,
    MeterModel,
    MeterProfile,
    MeterStatusHistory,
)
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
    MeterStatusHistoryResponse,
    MeterUpdate,
)
from app.modules.users.models import User


def _meter_options():
    return (
        selectinload(Meter.manufacturer),
        selectinload(Meter.meter_model),
        selectinload(Meter.firmware_version),
        selectinload(Meter.communication_profile),
        selectinload(Meter.meter_profile),
        selectinload(Meter.status_history),
    )


def list_manufacturers(session: Session) -> MeterManufacturerListResponse:
    total = session.scalar(select(func.count()).select_from(MeterManufacturer)) or 0
    items = session.scalars(select(MeterManufacturer).order_by(MeterManufacturer.name.asc())).all()
    return MeterManufacturerListResponse(
        total=total,
        items=[serialize_manufacturer(item) for item in items],
    )


def create_manufacturer(session: Session, payload: MeterManufacturerCreate) -> MeterManufacturer:
    existing = session.scalar(select(MeterManufacturer).where(func.lower(MeterManufacturer.code) == payload.code.lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manufacturer code already exists.")

    manufacturer = MeterManufacturer(
        name=payload.name.strip(),
        code=payload.code.strip().lower(),
        country=payload.country,
        website=payload.website,
        is_active=payload.is_active,
    )
    session.add(manufacturer)
    session.commit()
    session.refresh(manufacturer)
    return manufacturer


def list_meter_models(session: Session) -> MeterModelListResponse:
    total = session.scalar(select(func.count()).select_from(MeterModel)) or 0
    items = session.scalars(
        select(MeterModel)
        .options(selectinload(MeterModel.manufacturer))
        .order_by(MeterModel.display_name.asc())
    ).all()
    return MeterModelListResponse(total=total, items=[serialize_meter_model(item) for item in items])


def create_meter_model(session: Session, payload: MeterModelCreate) -> MeterModel:
    manufacturer = session.get(MeterManufacturer, payload.manufacturer_id)
    if manufacturer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manufacturer not found.")

    existing = session.scalar(
        select(MeterModel).where(
            MeterModel.manufacturer_id == payload.manufacturer_id,
            func.lower(MeterModel.model_code) == payload.model_code.lower(),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Meter model code already exists for this manufacturer.",
        )

    meter_model = MeterModel(
        manufacturer_id=payload.manufacturer_id,
        model_code=payload.model_code.strip().lower(),
        display_name=payload.display_name.strip(),
        phase_type=payload.phase_type,
        meter_category=payload.meter_category,
        dlms_capable=payload.dlms_capable,
        is_active=payload.is_active,
    )
    session.add(meter_model)
    session.commit()
    return get_meter_model_by_id(session, meter_model.id)


def get_meter_model_by_id(session: Session, meter_model_id: uuid.UUID) -> MeterModel:
    meter_model = session.scalar(
        select(MeterModel)
        .options(selectinload(MeterModel.manufacturer))
        .where(MeterModel.id == meter_model_id)
    )
    if meter_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter model not found.")
    return meter_model


def list_firmware_versions(session: Session) -> MeterFirmwareVersionListResponse:
    total = session.scalar(select(func.count()).select_from(MeterFirmwareVersion)) or 0
    items = session.scalars(
        select(MeterFirmwareVersion)
        .options(selectinload(MeterFirmwareVersion.meter_model))
        .order_by(MeterFirmwareVersion.version.asc())
    ).all()
    return MeterFirmwareVersionListResponse(
        total=total,
        items=[serialize_firmware_version(item) for item in items],
    )


def create_firmware_version(session: Session, payload: MeterFirmwareVersionCreate) -> MeterFirmwareVersion:
    meter_model = session.get(MeterModel, payload.meter_model_id)
    if meter_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter model not found.")

    existing = session.scalar(
        select(MeterFirmwareVersion).where(
            MeterFirmwareVersion.meter_model_id == payload.meter_model_id,
            func.lower(MeterFirmwareVersion.version) == payload.version.lower(),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Firmware version already exists for this meter model.",
        )

    firmware_version = MeterFirmwareVersion(
        meter_model_id=payload.meter_model_id,
        version=payload.version.strip(),
        release_notes=payload.release_notes,
        is_active=payload.is_active,
    )
    session.add(firmware_version)
    session.commit()
    return get_firmware_version_by_id(session, firmware_version.id)


def get_firmware_version_by_id(session: Session, firmware_version_id: uuid.UUID) -> MeterFirmwareVersion:
    firmware_version = session.scalar(
        select(MeterFirmwareVersion)
        .options(selectinload(MeterFirmwareVersion.meter_model))
        .where(MeterFirmwareVersion.id == firmware_version_id)
    )
    if firmware_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware version not found.")
    return firmware_version


def list_communication_profiles(session: Session) -> CommunicationProfileListResponse:
    total = session.scalar(select(func.count()).select_from(CommunicationProfile)) or 0
    items = session.scalars(select(CommunicationProfile).order_by(CommunicationProfile.name.asc())).all()
    return CommunicationProfileListResponse(
        total=total,
        items=[serialize_communication_profile(item) for item in items],
    )


def create_communication_profile(
    session: Session,
    payload: CommunicationProfileCreate,
) -> CommunicationProfile:
    existing = session.scalar(
        select(CommunicationProfile).where(func.lower(CommunicationProfile.code) == payload.code.lower())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Communication profile code already exists.",
        )

    profile = CommunicationProfile(
        code=payload.code.strip().lower(),
        name=payload.name.strip(),
        transport_type=payload.transport_type,
        ip_mode=payload.ip_mode,
        port=payload.port,
        apn=payload.apn,
        authentication_mode=payload.authentication_mode,
        protocol_settings=payload.protocol_settings,
        is_active=payload.is_active,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def list_meter_profiles(session: Session) -> MeterProfileListResponse:
    total = session.scalar(select(func.count()).select_from(MeterProfile)) or 0
    items = session.scalars(
        select(MeterProfile)
        .options(
            selectinload(MeterProfile.meter_model),
            selectinload(MeterProfile.communication_profile),
        )
        .order_by(MeterProfile.name.asc())
    ).all()
    return MeterProfileListResponse(total=total, items=[serialize_meter_profile(item) for item in items])


def create_meter_profile(session: Session, payload: MeterProfileCreate) -> MeterProfile:
    existing = session.scalar(select(MeterProfile).where(func.lower(MeterProfile.code) == payload.code.lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Meter profile code already exists.")

    meter_model = session.get(MeterModel, payload.meter_model_id)
    if meter_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter model not found.")

    communication_profile = None
    if payload.communication_profile_id is not None:
        communication_profile = session.get(CommunicationProfile, payload.communication_profile_id)
        if communication_profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Communication profile not found.",
            )

    meter_profile = MeterProfile(
        code=payload.code.strip().lower(),
        name=payload.name.strip(),
        meter_model_id=payload.meter_model_id,
        communication_profile_id=payload.communication_profile_id,
        protocol_family=payload.protocol_family,
        protocol_defaults=payload.protocol_defaults,
        description=payload.description,
        is_active=payload.is_active,
    )
    session.add(meter_profile)
    session.commit()
    return get_meter_profile_by_id(session, meter_profile.id)


def get_meter_profile_by_id(session: Session, meter_profile_id: uuid.UUID) -> MeterProfile:
    meter_profile = session.scalar(
        select(MeterProfile)
        .options(
            selectinload(MeterProfile.meter_model),
            selectinload(MeterProfile.communication_profile),
        )
        .where(MeterProfile.id == meter_profile_id)
    )
    if meter_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter profile not found.")
    return meter_profile


def list_meters(session: Session, *, offset: int = 0, limit: int = 50, search: str | None = None) -> MeterListResponse:
    base_statement = select(Meter)
    if search:
        pattern = f"%{search.strip().lower()}%"
        base_statement = base_statement.where(
            or_(
                func.lower(Meter.serial_number).like(pattern),
                func.lower(func.coalesce(Meter.utility_meter_number, "")).like(pattern),
                func.lower(func.coalesce(Meter.badge_number, "")).like(pattern),
            )
        )

    total = session.scalar(select(func.count()).select_from(base_statement.subquery())) or 0
    items = session.scalars(
        base_statement
        .options(*_meter_options())
        .order_by(Meter.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).unique().all()
    return MeterListResponse(total=total, items=[serialize_meter(item) for item in items])


def get_meter_by_id(session: Session, meter_id: uuid.UUID) -> Meter:
    meter = session.scalar(
        select(Meter)
        .options(*_meter_options())
        .where(Meter.id == meter_id)
    )
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found.")
    return meter


def create_meter(session: Session, payload: MeterCreate, *, changed_by_user_id: uuid.UUID | None) -> Meter:
    _ensure_unique_meter_identifiers(session, serial_number=payload.serial_number, utility_meter_number=payload.utility_meter_number)
    manufacturer = _require_entity(session, MeterManufacturer, payload.manufacturer_id, "Manufacturer")
    meter_model = _require_entity(session, MeterModel, payload.meter_model_id, "Meter model")

    if manufacturer.id != meter_model.manufacturer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meter model does not belong to the specified manufacturer.",
        )

    firmware_version = _validate_firmware_version(session, payload.firmware_version_id, meter_model.id)
    communication_profile = _validate_communication_profile(session, payload.communication_profile_id)
    meter_profile = _validate_meter_profile(session, payload.meter_profile_id, meter_model.id)
    if meter_profile is not None and communication_profile is not None:
        if (
            meter_profile.communication_profile_id is not None
            and meter_profile.communication_profile_id != communication_profile.id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Meter profile does not match the supplied communication profile.",
            )

    meter = Meter(
        serial_number=payload.serial_number.strip(),
        utility_meter_number=payload.utility_meter_number,
        badge_number=payload.badge_number,
        manufacturer_id=payload.manufacturer_id,
        meter_model_id=payload.meter_model_id,
        firmware_version_id=firmware_version.id if firmware_version is not None else None,
        communication_profile_id=communication_profile.id if communication_profile is not None else None,
        meter_profile_id=meter_profile.id if meter_profile is not None else None,
        transformer_id=payload.transformer_id,
        service_point_id=payload.service_point_id,
        current_status=payload.current_status,
        notes=payload.notes,
        is_active=payload.is_active,
        metadata_json=payload.metadata_json,
    )
    session.add(meter)
    session.flush()
    session.add(
        MeterStatusHistory(
            meter_id=meter.id,
            previous_status=None,
            new_status=payload.current_status,
            changed_by_user_id=changed_by_user_id,
            reason="Meter created.",
        )
    )
    session.commit()
    return get_meter_by_id(session, meter.id)


def update_meter(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: MeterUpdate,
) -> Meter:
    meter = get_meter_by_id(session, meter_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "utility_meter_number" in update_data:
        _ensure_unique_meter_identifiers(
            session,
            serial_number=meter.serial_number,
            utility_meter_number=update_data.get("utility_meter_number"),
            exclude_meter_id=meter.id,
        )
        meter.utility_meter_number = update_data.get("utility_meter_number")

    if "badge_number" in update_data:
        meter.badge_number = update_data.get("badge_number")

    if "firmware_version_id" in update_data:
        firmware_version = _validate_firmware_version(
            session,
            update_data["firmware_version_id"],
            meter.meter_model_id,
        )
        meter.firmware_version_id = firmware_version.id if firmware_version is not None else None

    if "communication_profile_id" in update_data:
        communication_profile = _validate_communication_profile(session, update_data["communication_profile_id"])
        meter.communication_profile_id = communication_profile.id if communication_profile is not None else None

    if "meter_profile_id" in update_data:
        meter_profile = _validate_meter_profile(session, update_data["meter_profile_id"], meter.meter_model_id)
        meter.meter_profile_id = meter_profile.id if meter_profile is not None else None

    for field in ("transformer_id", "service_point_id", "notes", "is_active", "metadata_json"):
        if field in update_data:
            setattr(meter, field, update_data[field])

    session.add(meter)
    session.commit()
    return get_meter_by_id(session, meter.id)


def change_meter_status(
    session: Session,
    *,
    meter_id: uuid.UUID,
    payload: MeterStatusChangeRequest,
    changed_by_user_id: uuid.UUID | None,
) -> Meter:
    meter = get_meter_by_id(session, meter_id)
    if meter.current_status == payload.new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meter already has the requested status.",
        )

    previous_status = meter.current_status
    meter.current_status = payload.new_status
    session.add(meter)
    session.flush()
    session.add(
        MeterStatusHistory(
            meter_id=meter.id,
            previous_status=previous_status,
            new_status=payload.new_status,
            changed_by_user_id=changed_by_user_id,
            reason=payload.reason,
        )
    )
    session.commit()
    return get_meter_by_id(session, meter.id)


def serialize_manufacturer(item: MeterManufacturer) -> MeterManufacturerResponse:
    return MeterManufacturerResponse.model_validate(item)


def serialize_meter_model(item: MeterModel) -> MeterModelResponse:
    return MeterModelResponse(
        id=item.id,
        manufacturer_id=item.manufacturer_id,
        manufacturer_code=item.manufacturer.code,
        model_code=item.model_code,
        display_name=item.display_name,
        phase_type=item.phase_type,
        meter_category=item.meter_category,
        dlms_capable=item.dlms_capable,
        is_active=item.is_active,
    )


def serialize_firmware_version(item: MeterFirmwareVersion) -> MeterFirmwareVersionResponse:
    return MeterFirmwareVersionResponse(
        id=item.id,
        meter_model_id=item.meter_model_id,
        meter_model_code=item.meter_model.model_code,
        version=item.version,
        release_notes=item.release_notes,
        is_active=item.is_active,
    )


def serialize_communication_profile(item: CommunicationProfile) -> CommunicationProfileResponse:
    return CommunicationProfileResponse(
        id=item.id,
        code=item.code,
        name=item.name,
        transport_type=item.transport_type,
        ip_mode=item.ip_mode,
        port=item.port,
        apn=item.apn,
        authentication_mode=item.authentication_mode,
        protocol_settings=item.protocol_settings,
        is_active=item.is_active,
    )


def serialize_meter_profile(item: MeterProfile) -> MeterProfileResponse:
    return MeterProfileResponse(
        id=item.id,
        code=item.code,
        name=item.name,
        meter_model_id=item.meter_model_id,
        meter_model_code=item.meter_model.model_code,
        communication_profile_id=item.communication_profile_id,
        communication_profile_code=item.communication_profile.code if item.communication_profile else None,
        protocol_family=item.protocol_family,
        protocol_defaults=item.protocol_defaults,
        description=item.description,
        is_active=item.is_active,
    )


def serialize_meter(item: Meter) -> MeterResponse:
    return MeterResponse(
        id=item.id,
        serial_number=item.serial_number,
        utility_meter_number=item.utility_meter_number,
        badge_number=item.badge_number,
        manufacturer_id=item.manufacturer_id,
        manufacturer_code=item.manufacturer.code,
        meter_model_id=item.meter_model_id,
        meter_model_code=item.meter_model.model_code,
        firmware_version_id=item.firmware_version_id,
        firmware_version=item.firmware_version.version if item.firmware_version else None,
        communication_profile_id=item.communication_profile_id,
        communication_profile_code=item.communication_profile.code if item.communication_profile else None,
        meter_profile_id=item.meter_profile_id,
        meter_profile_code=item.meter_profile.code if item.meter_profile else None,
        current_status=item.current_status,
        transformer_id=item.transformer_id,
        service_point_id=item.service_point_id,
        notes=item.notes,
        is_active=item.is_active,
        installed_at=item.installed_at,
        commissioned_at=item.commissioned_at,
        last_seen_at=item.last_seen_at,
        metadata_json=item.metadata_json,
    )


def serialize_meter_detail(item: Meter) -> MeterDetailResponse:
    response = serialize_meter(item)
    return MeterDetailResponse(
        **response.model_dump(),
        status_history=[
            MeterStatusHistoryResponse(
                id=history.id,
                previous_status=history.previous_status,
                new_status=history.new_status,
                changed_by_user_id=history.changed_by_user_id,
                reason=history.reason,
                changed_at=history.changed_at,
            )
            for history in sorted(item.status_history, key=lambda history: history.changed_at, reverse=True)
        ],
    )


def _ensure_unique_meter_identifiers(
    session: Session,
    *,
    serial_number: str,
    utility_meter_number: str | None,
    exclude_meter_id: uuid.UUID | None = None,
) -> None:
    serial_statement = select(Meter).where(func.lower(Meter.serial_number) == serial_number.strip().lower())
    if exclude_meter_id is not None:
        serial_statement = serial_statement.where(Meter.id != exclude_meter_id)
    if session.scalar(serial_statement) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Meter serial number already exists.")

    if utility_meter_number:
        utility_statement = select(Meter).where(
            func.lower(Meter.utility_meter_number) == utility_meter_number.strip().lower()
        )
        if exclude_meter_id is not None:
            utility_statement = utility_statement.where(Meter.id != exclude_meter_id)
        if session.scalar(utility_statement) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Utility meter number already exists.",
            )


def _require_entity(session: Session, model_class, entity_id: uuid.UUID, entity_name: str):
    entity = session.get(model_class, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity_name} not found.")
    return entity


def _validate_firmware_version(
    session: Session,
    firmware_version_id: uuid.UUID | None,
    meter_model_id: uuid.UUID,
) -> MeterFirmwareVersion | None:
    if firmware_version_id is None:
        return None
    firmware_version = session.get(MeterFirmwareVersion, firmware_version_id)
    if firmware_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware version not found.")
    if firmware_version.meter_model_id != meter_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firmware version does not belong to the selected meter model.",
        )
    return firmware_version


def _validate_communication_profile(
    session: Session,
    communication_profile_id: uuid.UUID | None,
) -> CommunicationProfile | None:
    if communication_profile_id is None:
        return None
    communication_profile = session.get(CommunicationProfile, communication_profile_id)
    if communication_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Communication profile not found.",
        )
    return communication_profile


def _validate_meter_profile(
    session: Session,
    meter_profile_id: uuid.UUID | None,
    meter_model_id: uuid.UUID,
) -> MeterProfile | None:
    if meter_profile_id is None:
        return None
    meter_profile = session.get(MeterProfile, meter_profile_id)
    if meter_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter profile not found.")
    if meter_profile.meter_model_id != meter_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meter profile does not belong to the selected meter model.",
        )
    return meter_profile
