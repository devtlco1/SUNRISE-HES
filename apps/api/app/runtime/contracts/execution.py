from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.modules.commands.enums import CommandCategory, CommandPriority
from app.modules.connectivity.enums import (
    AssociationAuthenticationMode,
    ConnectivityTransportType,
    ConnectivitySessionPurpose,
    ProtocolFamily,
    SerialParity,
    SerialStopBits,
)
from app.modules.jobs.enums import JobRunStatus
from app.modules.meters.enums import IPMode, TransportType


class RuntimeIntentType(StringEnum):
    ON_DEMAND_READ = "on_demand_read"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"
    CLOCK_SYNC = "clock_sync"
    READ_PROFILE = "read_profile"
    CONNECTIVITY_TEST = "connectivity_test"
    CONFIG_PUSH = "config_push"
    GENERIC_COMMAND = "generic_command"


class RuntimeStage(StringEnum):
    IEC62056_21 = "iec62056_21"
    HDLC = "hdlc"
    DLMS_COSEM = "dlms_cosem"
    GURUX_BRIDGE = "gurux_bridge"


class RuntimeExecutionContext(BaseModel):
    command_id: UUID
    job_run_id: UUID | None = None
    command_attempt_id: UUID | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    worker_identifier: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    triggered_at: datetime


class MeterRuntimeTarget(BaseModel):
    meter_id: UUID
    serial_number: str
    utility_meter_number: str | None = None
    meter_profile_id: UUID | None = None
    manufacturer_code: str
    meter_model_code: str
    meter_model_name: str
    endpoint_assignment_id: UUID
    endpoint_id: UUID
    endpoint_code: str
    protocol_association_profile_id: UUID


class RuntimeTransportConfig(BaseModel):
    endpoint_transport_type: ConnectivityTransportType
    communication_profile_transport_type: TransportType | None = None
    ip_mode: IPMode | None = None
    host: str | None = None
    port: int | None = None
    ip_address: str | None = None
    apn: str | None = None
    network_provider: str | None = None
    gateway_identifier: str | None = None
    serial_port_name: str | None = None
    baud_rate: int | None = None
    parity: SerialParity | None = None
    data_bits: int | None = None
    stop_bits: SerialStopBits | None = None


class RuntimeSecurityMaterialRefs(BaseModel):
    authentication_mode: AssociationAuthenticationMode
    password_secret_ref: str | None = None
    security_suite: str | None = None
    system_title: str | None = None
    auth_key_ref: str | None = None
    block_cipher_key_ref: str | None = None
    dedicated_key_ref: str | None = None


class RuntimeCommandRequest(BaseModel):
    command_id: UUID
    command_template_id: UUID
    command_template_code: str
    command_template_name: str
    category: CommandCategory
    intent: RuntimeIntentType
    priority: CommandPriority
    requested_at: datetime
    scheduled_at: datetime | None = None
    timeout_seconds: int
    max_retries: int
    request_payload: dict[str, object] | None = None
    normalized_payload: dict[str, object] | None = None


class ProtocolExecutionPlan(BaseModel):
    adapter_key: str
    protocol_family: ProtocolFamily
    intent: RuntimeIntentType
    stages: list[RuntimeStage]
    execution_context: RuntimeExecutionContext
    target: MeterRuntimeTarget
    command: RuntimeCommandRequest
    transport: RuntimeTransportConfig
    security: RuntimeSecurityMaterialRefs
    communication_profile_id: UUID | None = None
    communication_profile_code: str | None = None
    protocol_profile_code: str
    iec62056_21_enabled: bool = False
    iec_device_address: str | None = None
    iec_baud_rate: int | None = None
    client_address: int
    server_address: int
    server_address_size: int = 1
    protocol_settings: dict[str, object] | None = None
    protocol_defaults: dict[str, object] | None = None
    session_purpose: ConnectivitySessionPurpose
    job_run_status: JobRunStatus | None = None
