import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.audit.service import record_audit_event
from app.modules.auth.dependencies import require_permission
from app.modules.commands.profile_capture_execute_now import execute_profile_capture_now
from app.modules.commands.relay_control_execute_now import execute_relay_control_now
from app.modules.commands.relay_control_status_readback import (
    get_relay_control_execution_status,
)
from app.modules.commands.profile_capture_execution_orchestration import (
    orchestrate_profile_capture_command_execution,
)
from app.modules.commands.relay_control_execution_orchestration import (
    orchestrate_relay_control_command_execution,
)
from app.modules.commands.relay_control_runtime_handoff import (
    handoff_relay_control_command_to_runtime,
)
from app.modules.commands.relay_control_runtime_terminalization import (
    terminalize_relay_control_runtime_execution,
)
from app.modules.commands.profile_capture_status_readback import (
    get_profile_capture_execution_status,
)
from app.modules.commands.profile_capture_runtime_handoff import (
    handoff_profile_capture_command_to_runtime,
)
from app.modules.commands.profile_capture_runtime_terminalization import (
    terminalize_profile_capture_runtime_execution,
)
from app.modules.commands.schemas import (
    CaptureLoadProfileCommandCreate,
    CommandExecutionAttemptListResponse,
    CommandTemplateCreate,
    CommandTemplateListResponse,
    CommandTemplateResponse,
    CommandTemplateUpdate,
    MeterCommandCreate,
    MeterCommandDetailResponse,
    MeterCommandListResponse,
    MeterCommandResponse,
    ProfileCaptureAttemptBootstrapRequest,
    ProfileCaptureAttemptBootstrapResponse,
    ProfileCaptureExecuteNowRequest,
    ProfileCaptureExecuteNowResponse,
    ProfileCaptureExecutionStatusResponse,
    ProfileCaptureExecutionOrchestrationRequest,
    ProfileCaptureExecutionOrchestrationResponse,
    ProfileCaptureRuntimeHandoffRequest,
    ProfileCaptureRuntimeHandoffResponse,
    ProfileCaptureRuntimeTerminalizationRequest,
    ProfileCaptureRuntimeTerminalizationResponse,
    RelayControlAttemptBootstrapRequest,
    RelayControlAttemptBootstrapResponse,
    RelayControlExecuteNowRequest,
    RelayControlExecuteNowResponse,
    RelayControlExecutionOrchestrationRequest,
    RelayControlExecutionOrchestrationResponse,
    RelayControlExecutionStatusResponse,
    RelayControlRuntimeHandoffRequest,
    RelayControlRuntimeHandoffResponse,
    RelayControlRuntimeTerminalizationRequest,
    RelayControlRuntimeTerminalizationResponse,
    RelayControlCommandCreate,
)
from app.modules.jobs.dependencies import require_internal_api_token
from app.modules.commands.service import (
    bootstrap_profile_capture_command_attempt,
    bootstrap_relay_control_command_attempt,
    create_command_template,
    create_meter_command,
    submit_capture_load_profile_command,
    submit_relay_control_command,
    get_meter_command,
    get_command_template,
    list_command_attempts,
    list_command_templates,
    list_meter_commands,
    serialize_command_template,
    serialize_meter_command,
    serialize_meter_command_detail,
    update_command_template,
)
from app.modules.users.models import User

command_templates_router = APIRouter(prefix="/command-templates", tags=["command-templates"])
meter_commands_router = APIRouter(prefix="/meters", tags=["meter-commands"])
commands_router = APIRouter(prefix="/commands", tags=["commands"])
internal_commands_router = APIRouter(prefix="/internal/commands", tags=["internal-commands"])


@command_templates_router.get("", response_model=CommandTemplateListResponse)
def list_command_templates_endpoint(
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("commands.templates.read")),
) -> CommandTemplateListResponse:
    return list_command_templates(session)


@command_templates_router.post("", response_model=CommandTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_command_template_endpoint(
    payload: CommandTemplateCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.templates.write")),
) -> CommandTemplateResponse:
    template = create_command_template(session, payload)
    response = serialize_command_template(template)
    record_audit_event(
        session,
        action="commands.templates.create",
        resource_type="command_templates",
        resource_id=template.id,
        actor_user_id=current_user.id,
        description="Command template created.",
        details={"code": template.code, "category": template.category.value},
        request_context=request.state.request_audit_context,
    )
    return response


@command_templates_router.get("/{template_id}", response_model=CommandTemplateResponse)
def get_command_template_endpoint(
    template_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("commands.templates.read")),
) -> CommandTemplateResponse:
    template = get_command_template(session, template_id)
    return serialize_command_template(template)


@command_templates_router.patch("/{template_id}", response_model=CommandTemplateResponse)
def update_command_template_endpoint(
    template_id: uuid.UUID,
    payload: CommandTemplateUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.templates.write")),
) -> CommandTemplateResponse:
    template = update_command_template(session, template_id=template_id, payload=payload)
    response = serialize_command_template(template)
    record_audit_event(
        session,
        action="commands.templates.update",
        resource_type="command_templates",
        resource_id=template.id,
        actor_user_id=current_user.id,
        description="Command template updated.",
        details=payload.model_dump(exclude_unset=True),
        request_context=request.state.request_audit_context,
    )
    return response


@meter_commands_router.post(
    "/{meter_id}/commands/profile-capture",
    response_model=MeterCommandResponse,
)
def submit_capture_load_profile_command_endpoint(
    meter_id: uuid.UUID,
    payload: CaptureLoadProfileCommandCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.execute.request")),
) -> MeterCommandResponse:
    command = submit_capture_load_profile_command(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=current_user.id,
    )
    response = serialize_meter_command(command)
    record_audit_event(
        session,
        action="commands.requests.create_profile_capture",
        resource_type="commands",
        resource_id=command.id,
        actor_user_id=current_user.id,
        description="Capture-load-profile command requested.",
        details={
            "meter_id": str(meter_id),
            "template_code": command.command_template.code,
            "priority": command.priority.value,
            "idempotency_key": command.idempotency_key,
            "profile_read_operation": "capture_load_profile",
        },
        request_context=request.state.request_audit_context,
    )
    return response


@meter_commands_router.post(
    "/{meter_id}/commands/profile-capture/execute-now",
    response_model=ProfileCaptureExecuteNowResponse,
)
def execute_profile_capture_now_endpoint(
    meter_id: uuid.UUID,
    payload: ProfileCaptureExecuteNowRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.execute.request")),
) -> ProfileCaptureExecuteNowResponse:
    response = execute_profile_capture_now(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=current_user.id,
    )
    record_audit_event(
        session,
        action="commands.requests.execute_profile_capture_now",
        resource_type="commands",
        resource_id=response.result.command_id,
        actor_user_id=current_user.id,
        description="Capture-load-profile command executed through application-facing execute-now path.",
        details={
            "meter_id": str(meter_id),
            "command_id": str(response.result.command_id),
            "command_execution_attempt_id": str(response.result.command_execution_attempt_id),
            "execute_now_identifier": response.result.execute_now_identifier,
            "runtime_profile_read_execution_record_id": response.result.runtime_profile_read_execution_record_id,
            "terminal_status_category": response.result.terminal_status_category,
            "reused_existing_execute_now": response.result.reused_existing_execute_now,
        },
        request_context=request.state.request_audit_context,
    )
    return response


@meter_commands_router.post(
    "/{meter_id}/commands/relay-control",
    response_model=MeterCommandResponse,
)
def submit_relay_control_command_endpoint(
    meter_id: uuid.UUID,
    payload: RelayControlCommandCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.execute.request")),
) -> MeterCommandResponse:
    command = submit_relay_control_command(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=current_user.id,
    )
    response = serialize_meter_command(command)
    record_audit_event(
        session,
        action="commands.requests.create_relay_control",
        resource_type="commands",
        resource_id=command.id,
        actor_user_id=current_user.id,
        description="Relay-control command requested.",
        details={
            "meter_id": str(meter_id),
            "template_code": command.command_template.code,
            "priority": command.priority.value,
            "idempotency_key": command.idempotency_key,
            "relay_control_operation": command.normalized_payload.get("relay_control_operation")
            if isinstance(command.normalized_payload, dict)
            else None,
        },
        request_context=request.state.request_audit_context,
    )
    return response


@meter_commands_router.post(
    "/{meter_id}/commands/relay-control/execute-now",
    response_model=RelayControlExecuteNowResponse,
)
def execute_relay_control_now_endpoint(
    meter_id: uuid.UUID,
    payload: RelayControlExecuteNowRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.execute.request")),
) -> RelayControlExecuteNowResponse:
    response = execute_relay_control_now(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=current_user.id,
    )
    record_audit_event(
        session,
        action="commands.requests.execute_relay_control_now",
        resource_type="commands",
        resource_id=response.result.command_id,
        actor_user_id=current_user.id,
        description="Relay-control command executed through application-facing execute-now path.",
        details={
            "meter_id": str(meter_id),
            "command_id": str(response.result.command_id),
            "command_execution_attempt_id": str(response.result.command_execution_attempt_id),
            "execute_now_identifier": response.result.execute_now_identifier,
            "runtime_relay_control_execution_record_id": (
                response.result.runtime_relay_control_execution_record_id
            ),
            "relay_control_execution_outcome": response.result.relay_control_execution_outcome,
            "reused_existing_execute_now": response.result.reused_existing_execute_now,
        },
        request_context=request.state.request_audit_context,
    )
    return response


@meter_commands_router.post(
    "/{meter_id}/commands",
    response_model=MeterCommandResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_meter_command_endpoint(
    meter_id: uuid.UUID,
    payload: MeterCommandCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(require_permission("commands.execute.request")),
) -> MeterCommandResponse:
    command = create_meter_command(
        session,
        meter_id=meter_id,
        payload=payload,
        requested_by_user_id=current_user.id,
    )
    response = serialize_meter_command(command)
    record_audit_event(
        session,
        action="commands.requests.create",
        resource_type="commands",
        resource_id=command.id,
        actor_user_id=current_user.id,
        description="Meter command requested.",
        details={
            "meter_id": str(meter_id),
            "template_code": command.command_template.code,
            "priority": command.priority.value,
            "idempotency_key": command.idempotency_key,
        },
        request_context=request.state.request_audit_context,
    )
    return response


@meter_commands_router.get("/{meter_id}/commands", response_model=MeterCommandListResponse)
def list_meter_commands_endpoint(
    meter_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("commands.read")),
) -> MeterCommandListResponse:
    return list_meter_commands(session, meter_id=meter_id, limit=limit)


@commands_router.get("/{command_id}", response_model=MeterCommandDetailResponse)
def get_command_endpoint(
    command_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("commands.read")),
) -> MeterCommandDetailResponse:
    command = get_meter_command(session, command_id)
    return serialize_meter_command_detail(command)


@commands_router.get(
    "/{command_id}/relay-control-status",
    response_model=RelayControlExecutionStatusResponse,
)
def get_relay_control_status_endpoint(
    command_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("commands.read")),
) -> RelayControlExecutionStatusResponse:
    return get_relay_control_execution_status(session, command_id=command_id)


@commands_router.get(
    "/{command_id}/profile-capture-status",
    response_model=ProfileCaptureExecutionStatusResponse,
)
def get_profile_capture_status_endpoint(
    command_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("commands.read")),
) -> ProfileCaptureExecutionStatusResponse:
    return get_profile_capture_execution_status(session, command_id=command_id)


@commands_router.get("/{command_id}/attempts", response_model=CommandExecutionAttemptListResponse)
def list_command_attempts_endpoint(
    command_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("commands.read")),
) -> CommandExecutionAttemptListResponse:
    return list_command_attempts(session, command_id=command_id)


@internal_commands_router.post(
    "/{command_id}/bootstrap-profile-capture-attempt",
    response_model=ProfileCaptureAttemptBootstrapResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bootstrap_profile_capture_attempt_endpoint(
    command_id: uuid.UUID,
    payload: ProfileCaptureAttemptBootstrapRequest,
    session: Session = Depends(get_db_session),
) -> ProfileCaptureAttemptBootstrapResponse:
    return bootstrap_profile_capture_command_attempt(
        session,
        command_id=command_id,
        payload=payload,
    )


@internal_commands_router.post(
    "/{command_id}/bootstrap-relay-control-attempt",
    response_model=RelayControlAttemptBootstrapResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def bootstrap_relay_control_attempt_endpoint(
    command_id: uuid.UUID,
    payload: RelayControlAttemptBootstrapRequest,
    session: Session = Depends(get_db_session),
) -> RelayControlAttemptBootstrapResponse:
    return bootstrap_relay_control_command_attempt(
        session,
        command_id=command_id,
        payload=payload,
    )


@internal_commands_router.post(
    "/{command_id}/handoff-relay-control-to-runtime",
    response_model=RelayControlRuntimeHandoffResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def handoff_relay_control_to_runtime_endpoint(
    command_id: uuid.UUID,
    payload: RelayControlRuntimeHandoffRequest,
    session: Session = Depends(get_db_session),
) -> RelayControlRuntimeHandoffResponse:
    return handoff_relay_control_command_to_runtime(
        session,
        command_id=command_id,
        payload=payload,
    )


@internal_commands_router.post(
    "/{command_id}/terminalize-relay-control-runtime",
    response_model=RelayControlRuntimeTerminalizationResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def terminalize_relay_control_runtime_endpoint(
    command_id: uuid.UUID,
    payload: RelayControlRuntimeTerminalizationRequest,
    session: Session = Depends(get_db_session),
) -> RelayControlRuntimeTerminalizationResponse:
    return terminalize_relay_control_runtime_execution(
        session,
        command_id=command_id,
        payload=payload,
    )


@internal_commands_router.post(
    "/{command_id}/execute-relay-control-in-process",
    response_model=RelayControlExecutionOrchestrationResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def execute_relay_control_in_process_endpoint(
    command_id: uuid.UUID,
    payload: RelayControlExecutionOrchestrationRequest,
    session: Session = Depends(get_db_session),
) -> RelayControlExecutionOrchestrationResponse:
    return orchestrate_relay_control_command_execution(
        session,
        command_id=command_id,
        payload=payload,
    )


@internal_commands_router.post(
    "/{command_id}/handoff-profile-capture-to-runtime",
    response_model=ProfileCaptureRuntimeHandoffResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def handoff_profile_capture_to_runtime_endpoint(
    command_id: uuid.UUID,
    payload: ProfileCaptureRuntimeHandoffRequest,
    session: Session = Depends(get_db_session),
) -> ProfileCaptureRuntimeHandoffResponse:
    return handoff_profile_capture_command_to_runtime(
        session,
        command_id=command_id,
        payload=payload,
    )


@internal_commands_router.post(
    "/{command_id}/terminalize-profile-capture-runtime",
    response_model=ProfileCaptureRuntimeTerminalizationResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def terminalize_profile_capture_runtime_endpoint(
    command_id: uuid.UUID,
    payload: ProfileCaptureRuntimeTerminalizationRequest,
    session: Session = Depends(get_db_session),
) -> ProfileCaptureRuntimeTerminalizationResponse:
    return terminalize_profile_capture_runtime_execution(
        session,
        command_id=command_id,
        payload=payload,
    )


@internal_commands_router.post(
    "/{command_id}/execute-profile-capture-in-process",
    response_model=ProfileCaptureExecutionOrchestrationResponse,
    dependencies=[Depends(require_internal_api_token)],
)
def execute_profile_capture_in_process_endpoint(
    command_id: uuid.UUID,
    payload: ProfileCaptureExecutionOrchestrationRequest,
    session: Session = Depends(get_db_session),
) -> ProfileCaptureExecutionOrchestrationResponse:
    return orchestrate_profile_capture_command_execution(
        session,
        command_id=command_id,
        payload=payload,
    )
