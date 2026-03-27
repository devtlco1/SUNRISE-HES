from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

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


class CommunicationEndpointCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=2, max_length=255)
    endpoint_type: CommunicationEndpointType
    transport_type: ConnectivityTransportType
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    serial_port_name: str | None = Field(default=None, max_length=255)
    baud_rate: int | None = Field(default=None, ge=300, le=921600)
    parity: SerialParity | None = None
    data_bits: int | None = Field(default=None, ge=5, le=8)
    stop_bits: SerialStopBits | None = None
    sim_iccid: str | None = Field(default=None, max_length=64)
    sim_msisdn: str | None = Field(default=None, max_length=64)
    imei: str | None = Field(default=None, max_length=64)
    ip_address: str | None = Field(default=None, max_length=64)
    apn: str | None = Field(default=None, max_length=255)
    network_provider: str | None = Field(default=None, max_length=128)
    gateway_identifier: str | None = Field(default=None, max_length=128)
    is_active: bool = True
    notes: str | None = None


class CommunicationEndpointUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=255)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    serial_port_name: str | None = Field(default=None, max_length=255)
    baud_rate: int | None = Field(default=None, ge=300, le=921600)
    parity: SerialParity | None = None
    data_bits: int | None = Field(default=None, ge=5, le=8)
    stop_bits: SerialStopBits | None = None
    sim_iccid: str | None = Field(default=None, max_length=64)
    sim_msisdn: str | None = Field(default=None, max_length=64)
    imei: str | None = Field(default=None, max_length=64)
    ip_address: str | None = Field(default=None, max_length=64)
    apn: str | None = Field(default=None, max_length=255)
    network_provider: str | None = Field(default=None, max_length=128)
    gateway_identifier: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None
    notes: str | None = None


class CommunicationEndpointResponse(BaseModel):
    id: UUID
    code: str
    display_name: str
    endpoint_type: CommunicationEndpointType
    transport_type: ConnectivityTransportType
    host: str | None
    port: int | None
    serial_port_name: str | None
    baud_rate: int | None
    parity: SerialParity | None
    data_bits: int | None
    stop_bits: SerialStopBits | None
    sim_iccid: str | None
    sim_msisdn: str | None
    imei: str | None
    ip_address: str | None
    apn: str | None
    network_provider: str | None
    gateway_identifier: str | None
    is_active: bool
    notes: str | None


class CommunicationEndpointListResponse(BaseModel):
    total: int
    items: list[CommunicationEndpointResponse]


class ProtocolAssociationProfileCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    protocol_family: ProtocolFamily = ProtocolFamily.DLMS_COSEM
    iec62056_21_enabled: bool = False
    iec_device_address: str | None = Field(default=None, max_length=128)
    iec_baud_rate: int | None = Field(default=None, ge=300, le=115200)
    client_address: int = Field(ge=1, le=65535)
    server_address: int = Field(ge=1, le=65535)
    authentication_mode: AssociationAuthenticationMode = AssociationAuthenticationMode.NONE
    password_secret_ref: str | None = Field(default=None, max_length=255)
    security_suite: str | None = Field(default=None, max_length=64)
    system_title: str | None = Field(default=None, max_length=64)
    auth_key_ref: str | None = Field(default=None, max_length=255)
    block_cipher_key_ref: str | None = Field(default=None, max_length=255)
    dedicated_key_ref: str | None = Field(default=None, max_length=255)
    invocation_counter_obis: str | None = Field(default=None, max_length=64)
    meter_time_obis: str | None = Field(default=None, max_length=64)
    profile_settings: dict[str, object] | None = None
    is_active: bool = True


class ProtocolAssociationProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    iec62056_21_enabled: bool | None = None
    iec_device_address: str | None = Field(default=None, max_length=128)
    iec_baud_rate: int | None = Field(default=None, ge=300, le=115200)
    client_address: int | None = Field(default=None, ge=1, le=65535)
    server_address: int | None = Field(default=None, ge=1, le=65535)
    authentication_mode: AssociationAuthenticationMode | None = None
    password_secret_ref: str | None = Field(default=None, max_length=255)
    security_suite: str | None = Field(default=None, max_length=64)
    system_title: str | None = Field(default=None, max_length=64)
    auth_key_ref: str | None = Field(default=None, max_length=255)
    block_cipher_key_ref: str | None = Field(default=None, max_length=255)
    dedicated_key_ref: str | None = Field(default=None, max_length=255)
    invocation_counter_obis: str | None = Field(default=None, max_length=64)
    meter_time_obis: str | None = Field(default=None, max_length=64)
    profile_settings: dict[str, object] | None = None
    is_active: bool | None = None


class ProtocolAssociationProfileResponse(BaseModel):
    id: UUID
    code: str
    name: str
    protocol_family: ProtocolFamily
    iec62056_21_enabled: bool
    iec_device_address: str | None
    iec_baud_rate: int | None
    client_address: int
    server_address: int
    authentication_mode: AssociationAuthenticationMode
    password_secret_ref: str | None
    security_suite: str | None
    system_title: str | None
    auth_key_ref: str | None
    block_cipher_key_ref: str | None
    dedicated_key_ref: str | None
    invocation_counter_obis: str | None
    meter_time_obis: str | None
    profile_settings: dict[str, object] | None
    is_active: bool


class ProtocolAssociationProfileListResponse(BaseModel):
    total: int
    items: list[ProtocolAssociationProfileResponse]


class ConnectivityCredentialCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    credential_type: CredentialType
    username: str | None = Field(default=None, max_length=255)
    secret_ref: str = Field(min_length=2, max_length=255)
    description: str | None = None
    is_active: bool = True


class ConnectivityCredentialUpdate(BaseModel):
    username: str | None = Field(default=None, max_length=255)
    secret_ref: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class ConnectivityCredentialResponse(BaseModel):
    id: UUID
    code: str
    credential_type: CredentialType
    username: str | None
    secret_ref: str
    description: str | None
    is_active: bool


class ConnectivityCredentialListResponse(BaseModel):
    total: int
    items: list[ConnectivityCredentialResponse]


class MeterEndpointAssignmentCreate(BaseModel):
    endpoint_id: UUID
    is_primary: bool = False
    assignment_status: EndpointAssignmentStatus = EndpointAssignmentStatus.ACTIVE
    notes: str | None = None


class MeterEndpointAssignmentResponse(BaseModel):
    id: UUID
    meter_id: UUID
    endpoint_id: UUID
    endpoint_code: str
    endpoint_display_name: str
    assigned_at: datetime
    unassigned_at: datetime | None
    is_primary: bool
    assignment_status: EndpointAssignmentStatus
    notes: str | None


class MeterEndpointAssignmentListResponse(BaseModel):
    total: int
    items: list[MeterEndpointAssignmentResponse]


class ConnectivitySessionHistoryResponse(BaseModel):
    id: UUID
    meter_id: UUID | None
    endpoint_id: UUID | None
    protocol_association_profile_id: UUID | None
    started_at: datetime
    ended_at: datetime | None
    status: ConnectivitySessionStatus
    session_purpose: ConnectivitySessionPurpose
    request_id: str | None
    correlation_id: str | None
    error_code: str | None
    error_message: str | None
    bytes_sent: int | None
    bytes_received: int | None
    transport_latency_ms: int | None
    handshake_stage: str | None
    metadata: dict[str, object] | None


class ConnectivitySessionHistoryListResponse(BaseModel):
    total: int
    items: list[ConnectivitySessionHistoryResponse]
