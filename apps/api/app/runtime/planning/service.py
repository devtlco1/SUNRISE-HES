from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commands.models import MeterCommand
from app.modules.commands.service import get_meter_command
from app.modules.connectivity.enums import (
    ConnectivitySessionPurpose,
    EndpointAssignmentStatus,
    ProtocolFamily,
)
from app.modules.connectivity.models import MeterEndpointAssignment, ProtocolAssociationProfile
from app.modules.jobs.models import JobRun
from app.modules.meters.models import Meter
from app.runtime.adapters import get_runtime_adapter_for_protocol
from app.runtime.contracts import (
    MeterRuntimeTarget,
    ProtocolExecutionPlan,
    RuntimeCommandRequest,
    RuntimeExecutionContext,
    RuntimeSecurityMaterialRefs,
    RuntimeStage,
    RuntimeTransportConfig,
)
from app.runtime.planning.intents import map_command_category_to_runtime_intent


def resolve_protocol_execution_plan(
    session: Session,
    *,
    command_id: UUID,
    worker_identifier: str | None = None,
    request_id: str | None = None,
) -> ProtocolExecutionPlan:
    command = get_meter_command(session, command_id)
    meter = session.get(Meter, command.meter_id)
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found for command.")

    endpoint_assignment = _resolve_endpoint_assignment(session, command)
    endpoint = endpoint_assignment.endpoint
    if endpoint is None or not endpoint.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime planning requires an active communication endpoint.",
        )

    protocol_profile = _resolve_protocol_association_profile(session, command)
    if not protocol_profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime planning requires an active protocol association profile.",
        )

    communication_profile = meter.communication_profile or (
        meter.meter_profile.communication_profile if meter.meter_profile is not None else None
    )
    intent = map_command_category_to_runtime_intent(command.command_template.category)
    try:
        adapter = get_runtime_adapter_for_protocol(protocol_profile.protocol_family)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    job_run = session.scalar(
        select(JobRun)
        .where(JobRun.related_command_id == command.id)
        .order_by(JobRun.scheduled_for.desc())
    )

    normalized_payload = _build_runtime_payload(
        command=command,
        meter=meter,
        endpoint_assignment=endpoint_assignment,
        protocol_profile=protocol_profile,
        communication_profile=communication_profile,
        job_run=job_run,
    )
    stages = _resolve_runtime_stages(protocol_profile.protocol_family, protocol_profile.iec62056_21_enabled)
    session_purpose = _resolve_session_purpose(intent)

    return ProtocolExecutionPlan(
        adapter_key=adapter.adapter_key,
        protocol_family=protocol_profile.protocol_family,
        intent=intent,
        stages=stages,
        execution_context=RuntimeExecutionContext(
            command_id=command.id,
            job_run_id=job_run.id if job_run is not None else None,
            command_attempt_id=None,
            correlation_id=command.correlation_id,
            worker_identifier=worker_identifier,
            request_id=request_id,
            triggered_at=datetime.now(UTC),
        ),
        target=MeterRuntimeTarget(
            meter_id=meter.id,
            serial_number=meter.serial_number,
            utility_meter_number=meter.utility_meter_number,
            meter_profile_id=meter.meter_profile_id,
            manufacturer_code=meter.manufacturer.code,
            meter_model_code=meter.meter_model.model_code,
            meter_model_name=meter.meter_model.display_name,
            endpoint_assignment_id=endpoint_assignment.id,
            endpoint_id=endpoint.id,
            endpoint_code=endpoint.code,
            protocol_association_profile_id=protocol_profile.id,
        ),
        command=RuntimeCommandRequest(
            command_id=command.id,
            command_template_id=command.command_template_id,
            command_template_code=command.command_template.code,
            command_template_name=command.command_template.name,
            category=command.command_template.category,
            intent=intent,
            priority=command.priority,
            requested_at=command.requested_at,
            scheduled_at=command.scheduled_at,
            timeout_seconds=command.command_template.timeout_seconds,
            max_retries=command.max_retries,
            request_payload=command.request_payload,
            normalized_payload=normalized_payload,
        ),
        transport=RuntimeTransportConfig(
            endpoint_transport_type=endpoint.transport_type,
            communication_profile_transport_type=(
                communication_profile.transport_type if communication_profile is not None else None
            ),
            ip_mode=communication_profile.ip_mode if communication_profile is not None else None,
            host=endpoint.host,
            port=endpoint.port or (communication_profile.port if communication_profile is not None else None),
            ip_address=endpoint.ip_address,
            apn=endpoint.apn or (communication_profile.apn if communication_profile is not None else None),
            network_provider=endpoint.network_provider,
            gateway_identifier=endpoint.gateway_identifier,
            serial_port_name=endpoint.serial_port_name,
            baud_rate=endpoint.baud_rate,
            parity=endpoint.parity,
            data_bits=endpoint.data_bits,
            stop_bits=endpoint.stop_bits,
        ),
        security=RuntimeSecurityMaterialRefs(
            authentication_mode=protocol_profile.authentication_mode,
            password_secret_ref=protocol_profile.password_secret_ref,
            security_suite=protocol_profile.security_suite,
            system_title=protocol_profile.system_title,
            auth_key_ref=protocol_profile.auth_key_ref,
            block_cipher_key_ref=protocol_profile.block_cipher_key_ref,
            dedicated_key_ref=protocol_profile.dedicated_key_ref,
        ),
        communication_profile_id=communication_profile.id if communication_profile is not None else None,
        communication_profile_code=communication_profile.code if communication_profile is not None else None,
        protocol_profile_code=protocol_profile.code,
        protocol_settings=protocol_profile.profile_settings,
        protocol_defaults=meter.meter_profile.protocol_defaults if meter.meter_profile is not None else None,
        session_purpose=session_purpose,
        job_run_status=job_run.status if job_run is not None else None,
    )


def _resolve_endpoint_assignment(session: Session, command: MeterCommand) -> MeterEndpointAssignment:
    if command.endpoint_assignment_id is not None:
        assignment = session.get(MeterEndpointAssignment, command.endpoint_assignment_id)
        if assignment is None or assignment.meter_id != command.meter_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Runtime planning requires a valid endpoint assignment for the command meter.",
            )
    else:
        assignment = session.scalar(
            select(MeterEndpointAssignment)
            .where(
                MeterEndpointAssignment.meter_id == command.meter_id,
                MeterEndpointAssignment.assignment_status == EndpointAssignmentStatus.ACTIVE,
                MeterEndpointAssignment.unassigned_at.is_(None),
            )
            .order_by(
                MeterEndpointAssignment.is_primary.desc(),
                MeterEndpointAssignment.assigned_at.desc(),
            )
        )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime planning requires an active endpoint assignment.",
        )
    if assignment.assignment_status != EndpointAssignmentStatus.ACTIVE or assignment.unassigned_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime planning requires an active endpoint assignment.",
        )
    return assignment


def _resolve_protocol_association_profile(
    session: Session,
    command: MeterCommand,
) -> ProtocolAssociationProfile:
    profile_id = command.protocol_association_profile_id or _lookup_profile_id_from_payload(command)
    if profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime planning requires a protocol association profile.",
        )

    profile = session.get(ProtocolAssociationProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol association profile not found for runtime planning.",
        )
    return profile


def _lookup_profile_id_from_payload(command: MeterCommand) -> UUID | None:
    payloads = [command.normalized_payload, command.request_payload]
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        value = payload.get("protocol_association_profile_id")
        if not isinstance(value, str):
            continue
        try:
            return UUID(value)
        except ValueError:
            continue
    return None


def _build_runtime_payload(
    *,
    command: MeterCommand,
    meter: Meter,
    endpoint_assignment: MeterEndpointAssignment,
    protocol_profile: ProtocolAssociationProfile,
    communication_profile,
    job_run: JobRun | None,
) -> dict[str, object]:
    base_payload: dict[str, object] = {}
    if isinstance(command.normalized_payload, dict):
        base_payload.update(command.normalized_payload)
    elif isinstance(command.request_payload, dict):
        base_payload.update(command.request_payload)

    base_payload.setdefault("command_id", str(command.id))
    base_payload.setdefault("command_template_code", command.command_template.code)
    base_payload.setdefault("meter", {})
    meter_payload = base_payload["meter"]
    if isinstance(meter_payload, dict):
        meter_payload.setdefault("id", str(meter.id))
        meter_payload.setdefault("serial_number", meter.serial_number)
        meter_payload.setdefault("utility_meter_number", meter.utility_meter_number)

    base_payload["runtime"] = {
        "endpoint_assignment_id": str(endpoint_assignment.id),
        "endpoint_id": str(endpoint_assignment.endpoint_id),
        "protocol_association_profile_id": str(protocol_profile.id),
        "communication_profile_id": (
            str(communication_profile.id) if communication_profile is not None else None
        ),
        "job_run_id": str(job_run.id) if job_run is not None else None,
        "correlation_id": command.correlation_id,
    }
    return base_payload


def _resolve_runtime_stages(
    protocol_family: ProtocolFamily,
    iec62056_21_enabled: bool,
) -> list[RuntimeStage]:
    stages: list[RuntimeStage] = []
    if iec62056_21_enabled:
        stages.append(RuntimeStage.IEC62056_21)

    if protocol_family == ProtocolFamily.DLMS_COSEM:
        stages.extend(
            [
                RuntimeStage.HDLC,
                RuntimeStage.DLMS_COSEM,
                RuntimeStage.GURUX_BRIDGE,
            ]
        )
    return stages


def _resolve_session_purpose(intent) -> ConnectivitySessionPurpose:
    if intent.value == "connectivity_test":
        return ConnectivitySessionPurpose.CONNECTIVITY_TEST
    if intent.value == "read_profile":
        return ConnectivitySessionPurpose.PROFILE_VALIDATION
    return ConnectivitySessionPurpose.MANUAL_DIAGNOSTIC
