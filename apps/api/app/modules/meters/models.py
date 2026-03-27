from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.meters.enums import (
    AuthenticationMode,
    IPMode,
    MeterCategory,
    MeterLifecycleStatus,
    PhaseType,
    TransportType,
)


class MeterManufacturer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meter_manufacturers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str | None] = mapped_column(String(128))
    website: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    models: Mapped[list["MeterModel"]] = relationship(back_populates="manufacturer")
    meters: Mapped[list["Meter"]] = relationship(back_populates="manufacturer")

    __table_args__ = (
        UniqueConstraint("name"),
        UniqueConstraint("code"),
        Index("ix_meter_manufacturers_is_active", "is_active"),
    )


class MeterModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meter_models"

    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meter_manufacturers.id"),
        nullable=False,
    )
    model_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phase_type: Mapped[PhaseType] = mapped_column(
        enum_type(PhaseType, name="phase_type"),
        nullable=False,
    )
    meter_category: Mapped[MeterCategory] = mapped_column(
        enum_type(MeterCategory, name="meter_category"),
        nullable=False,
    )
    dlms_capable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    manufacturer: Mapped["MeterManufacturer"] = relationship(back_populates="models")
    firmware_versions: Mapped[list["MeterFirmwareVersion"]] = relationship(back_populates="meter_model")
    meter_profiles: Mapped[list["MeterProfile"]] = relationship(back_populates="meter_model")
    meters: Mapped[list["Meter"]] = relationship(back_populates="meter_model")

    __table_args__ = (
        UniqueConstraint("manufacturer_id", "model_code"),
        Index("ix_meter_models_manufacturer_id", "manufacturer_id"),
        Index("ix_meter_models_meter_category", "meter_category"),
        Index("ix_meter_models_is_active", "is_active"),
    )


class MeterProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meter_profiles"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    meter_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_models.id"), nullable=False)
    communication_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communication_profiles.id")
    )
    protocol_family: Mapped[str | None] = mapped_column(String(128))
    protocol_defaults: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    meter_model: Mapped["MeterModel"] = relationship(back_populates="meter_profiles")
    communication_profile: Mapped[CommunicationProfile | None] = relationship(
        back_populates="meter_profiles"
    )
    meters: Mapped[list["Meter"]] = relationship(back_populates="meter_profile")

    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_meter_profiles_meter_model_id", "meter_model_id"),
        Index("ix_meter_profiles_is_active", "is_active"),
    )


class MeterFirmwareVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meter_firmware_versions"

    meter_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_models.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    release_notes: Mapped[str | None] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    meter_model: Mapped["MeterModel"] = relationship(back_populates="firmware_versions")
    meters: Mapped[list["Meter"]] = relationship(back_populates="firmware_version")

    __table_args__ = (
        UniqueConstraint("meter_model_id", "version"),
        Index("ix_meter_firmware_versions_meter_model_id", "meter_model_id"),
        Index("ix_meter_firmware_versions_is_active", "is_active"),
    )


class CommunicationProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "communication_profiles"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    transport_type: Mapped[TransportType] = mapped_column(
        enum_type(TransportType, name="transport_type"),
        nullable=False,
    )
    ip_mode: Mapped[IPMode | None] = mapped_column(enum_type(IPMode, name="ip_mode"))
    port: Mapped[int | None] = mapped_column(Integer)
    apn: Mapped[str | None] = mapped_column(String(255))
    authentication_mode: Mapped[AuthenticationMode | None] = mapped_column(
        enum_type(AuthenticationMode, name="authentication_mode")
    )
    protocol_settings: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    meter_profiles: Mapped[list["MeterProfile"]] = relationship(back_populates="communication_profile")
    meters: Mapped[list["Meter"]] = relationship(back_populates="communication_profile")

    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_communication_profiles_transport_type", "transport_type"),
        Index("ix_communication_profiles_is_active", "is_active"),
    )


class Meter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meters"

    serial_number: Mapped[str] = mapped_column(String(128), nullable=False)
    utility_meter_number: Mapped[str | None] = mapped_column(String(128))
    badge_number: Mapped[str | None] = mapped_column(String(128))
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_manufacturers.id"), nullable=False)
    meter_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meter_models.id"), nullable=False)
    meter_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meter_profiles.id"))
    firmware_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meter_firmware_versions.id"))
    communication_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communication_profiles.id"),
    )
    transformer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transformers.id"))
    service_point_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("service_points.id"))
    current_status: Mapped[MeterLifecycleStatus] = mapped_column(
        enum_type(MeterLifecycleStatus, name="meter_lifecycle_status"),
        nullable=False,
        server_default=MeterLifecycleStatus.REGISTERED.value,
    )
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commissioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    manufacturer: Mapped["MeterManufacturer"] = relationship(back_populates="meters")
    meter_model: Mapped["MeterModel"] = relationship(back_populates="meters")
    meter_profile: Mapped[MeterProfile | None] = relationship(back_populates="meters")
    firmware_version: Mapped[MeterFirmwareVersion | None] = relationship(back_populates="meters")
    communication_profile: Mapped[CommunicationProfile | None] = relationship(back_populates="meters")
    status_history: Mapped[list["MeterStatusHistory"]] = relationship(back_populates="meter")

    __table_args__ = (
        UniqueConstraint("serial_number"),
        UniqueConstraint("utility_meter_number"),
        Index("ix_meters_current_status", "current_status"),
        Index("ix_meters_transformer_id", "transformer_id"),
        Index("ix_meters_service_point_id", "service_point_id"),
        Index("ix_meters_model_id", "meter_model_id"),
        Index("ix_meters_manufacturer_id", "manufacturer_id"),
        Index("ix_meters_communication_profile_id", "communication_profile_id"),
        Index("ix_meters_is_active", "is_active"),
    )


class MeterStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "meter_status_history"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    previous_status: Mapped[MeterLifecycleStatus | None] = mapped_column(
        enum_type(MeterLifecycleStatus, name="meter_lifecycle_status"),
    )
    new_status: Mapped[MeterLifecycleStatus] = mapped_column(
        enum_type(MeterLifecycleStatus, name="meter_lifecycle_status"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text())
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    meter: Mapped["Meter"] = relationship(back_populates="status_history")

    __table_args__ = (
        Index("ix_meter_status_history_meter_changed_at", "meter_id", "changed_at"),
        Index("ix_meter_status_history_meter_new_status", "meter_id", "new_status"),
    )
