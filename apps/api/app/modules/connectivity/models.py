from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import enum_type
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.connectivity.enums import (
    AssociationAuthenticationMode,
    CommunicationEndpointType,
    ConnectivitySessionPurpose,
    ConnectivitySessionStatus,
    ConnectivityTransportType,
    CredentialType,
    EndpointAssignmentStatus,
    ProtocolFamily,
    SerialParity,
    SerialStopBits,
)


class CommunicationEndpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "communication_endpoints"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint_type: Mapped[CommunicationEndpointType] = mapped_column(
        enum_type(CommunicationEndpointType, name="communication_endpoint_type"),
        nullable=False,
    )
    transport_type: Mapped[ConnectivityTransportType] = mapped_column(
        enum_type(ConnectivityTransportType, name="connectivity_transport_type"),
        nullable=False,
    )
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer)
    serial_port_name: Mapped[str | None] = mapped_column(String(255))
    baud_rate: Mapped[int | None] = mapped_column(Integer)
    parity: Mapped[SerialParity | None] = mapped_column(enum_type(SerialParity, name="serial_parity"))
    data_bits: Mapped[int | None] = mapped_column(Integer)
    stop_bits: Mapped[SerialStopBits | None] = mapped_column(
        enum_type(SerialStopBits, name="serial_stop_bits")
    )
    sim_iccid: Mapped[str | None] = mapped_column(String(64))
    sim_msisdn: Mapped[str | None] = mapped_column(String(64))
    imei: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(INET())
    apn: Mapped[str | None] = mapped_column(String(255))
    network_provider: Mapped[str | None] = mapped_column(String(128))
    gateway_identifier: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text())

    assignments: Mapped[list["MeterEndpointAssignment"]] = relationship(back_populates="endpoint")
    sessions: Mapped[list["ConnectivitySessionHistory"]] = relationship(back_populates="endpoint")

    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_communication_endpoints_endpoint_type", "endpoint_type"),
        Index("ix_communication_endpoints_transport_type", "transport_type"),
        Index("ix_communication_endpoints_is_active", "is_active"),
    )


class MeterEndpointAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "meter_endpoint_assignments"

    meter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("communication_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    assignment_status: Mapped[EndpointAssignmentStatus] = mapped_column(
        enum_type(EndpointAssignmentStatus, name="endpoint_assignment_status"),
        nullable=False,
        server_default=EndpointAssignmentStatus.ACTIVE.value,
    )
    notes: Mapped[str | None] = mapped_column(Text())

    endpoint: Mapped["CommunicationEndpoint"] = relationship(back_populates="assignments")

    __table_args__ = (
        Index("ix_meter_endpoint_assignments_meter_active", "meter_id", "assignment_status", "assigned_at"),
        Index("ix_meter_endpoint_assignments_endpoint_active", "endpoint_id", "assignment_status"),
        Index("ix_meter_endpoint_assignments_meter_primary", "meter_id", "is_primary"),
    )


class ProtocolAssociationProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "protocol_association_profiles"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol_family: Mapped[ProtocolFamily] = mapped_column(
        enum_type(ProtocolFamily, name="protocol_family"),
        nullable=False,
        server_default=ProtocolFamily.DLMS_COSEM.value,
    )
    iec62056_21_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    iec_device_address: Mapped[str | None] = mapped_column(String(128))
    iec_baud_rate: Mapped[int | None] = mapped_column(Integer)
    client_address: Mapped[int] = mapped_column(Integer, nullable=False)
    server_address: Mapped[int] = mapped_column(Integer, nullable=False)
    authentication_mode: Mapped[AssociationAuthenticationMode] = mapped_column(
        enum_type(AssociationAuthenticationMode, name="association_authentication_mode"),
        nullable=False,
        server_default=AssociationAuthenticationMode.NONE.value,
    )
    password_secret_ref: Mapped[str | None] = mapped_column(String(255))
    security_suite: Mapped[str | None] = mapped_column(String(64))
    system_title: Mapped[str | None] = mapped_column(String(64))
    auth_key_ref: Mapped[str | None] = mapped_column(String(255))
    block_cipher_key_ref: Mapped[str | None] = mapped_column(String(255))
    dedicated_key_ref: Mapped[str | None] = mapped_column(String(255))
    invocation_counter_obis: Mapped[str | None] = mapped_column(String(64))
    meter_time_obis: Mapped[str | None] = mapped_column(String(64))
    profile_settings: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    sessions: Mapped[list["ConnectivitySessionHistory"]] = relationship(
        back_populates="protocol_association_profile"
    )

    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_protocol_association_profiles_protocol_family", "protocol_family"),
        Index("ix_protocol_association_profiles_is_active", "is_active"),
    )


class ConnectivityCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connectivity_credentials"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_type: Mapped[CredentialType] = mapped_column(
        enum_type(CredentialType, name="credential_type"),
        nullable=False,
    )
    username: Mapped[str | None] = mapped_column(String(255))
    secret_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_connectivity_credentials_is_active", "is_active"),
    )


class ConnectivitySessionHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "connectivity_session_history"

    meter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meters.id", ondelete="SET NULL"))
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communication_endpoints.id", ondelete="SET NULL")
    )
    protocol_association_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("protocol_association_profiles.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ConnectivitySessionStatus] = mapped_column(
        enum_type(ConnectivitySessionStatus, name="connectivity_session_status"),
        nullable=False,
    )
    session_purpose: Mapped[ConnectivitySessionPurpose] = mapped_column(
        enum_type(ConnectivitySessionPurpose, name="connectivity_session_purpose"),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(String(128))
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text())
    bytes_sent: Mapped[int | None] = mapped_column(Integer)
    bytes_received: Mapped[int | None] = mapped_column(Integer)
    transport_latency_ms: Mapped[int | None] = mapped_column(Integer)
    handshake_stage: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)

    endpoint: Mapped[CommunicationEndpoint | None] = relationship(back_populates="sessions")
    protocol_association_profile: Mapped[ProtocolAssociationProfile | None] = relationship(
        back_populates="sessions"
    )

    __table_args__ = (
        Index("ix_connectivity_session_history_meter_started_at", "meter_id", "started_at"),
        Index("ix_connectivity_session_history_endpoint_started_at", "endpoint_id", "started_at"),
        Index("ix_connectivity_session_history_status_started_at", "status", "started_at"),
        Index("ix_connectivity_session_history_recent_started_at", "started_at"),
        Index("ix_connectivity_session_history_correlation_id", "correlation_id"),
    )
