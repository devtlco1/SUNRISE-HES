from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.enums import StringEnum
from app.modules.connectivity.enums import ConnectivitySessionStatus
from app.modules.events.enums import EventSeverity, EventState


class DownstreamFollowUpActionType(StringEnum):
    RETRY = "retry"
    FOLLOWUP_SCHEDULE = "followup_schedule"


class DerivedWorkRoutingCategory(StringEnum):
    RETRY_PATH = "retry_path"
    FOLLOWUP_PATH = "followup_path"


class DerivedWorkPickupCategory(StringEnum):
    RETRY_PICKUP = "retry_pickup"
    FOLLOWUP_PICKUP = "followup_pickup"


class DerivedWorkHandlerCategory(StringEnum):
    RETRY_HANDLER = "retry_handler"
    FOLLOWUP_HANDLER = "followup_handler"


class DerivedWorkCoordinationCategory(StringEnum):
    RETRY_DISPATCH_READY = "retry_dispatch_ready"
    FOLLOWUP_DISPATCH_READY = "followup_dispatch_ready"


class DerivedWorkDispatchCategory(StringEnum):
    RETRY_DISPATCH_REQUEST = "retry_dispatch_request"
    FOLLOWUP_DISPATCH_REQUEST = "followup_dispatch_request"


class DerivedWorkEnqueueCategory(StringEnum):
    RETRY_ENQUEUE_RESULT = "retry_enqueue_result"
    FOLLOWUP_ENQUEUE_RESULT = "followup_enqueue_result"


class QueueEnqueueStatus(StringEnum):
    ACCEPTED = "accepted"


class EndpointHealthProjectionStatus(StringEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DownstreamFollowUpActionDescriptor(BaseModel):
    action_type: DownstreamFollowUpActionType
    reason: str
    payload: dict[str, object] | None = None


class EndpointHealthHint(BaseModel):
    status: EndpointHealthProjectionStatus
    reason: str
    should_mark_endpoint_unhealthy: bool
    session_status: ConnectivitySessionStatus


class OperationalEventArtifact(BaseModel):
    event_code: str = Field(min_length=1, max_length=128)
    event_name: str | None = Field(default=None, max_length=255)
    severity: EventSeverity
    event_state: EventState
    normalized_payload: dict[str, object] | None = None


class DownstreamSignalConsumptionResult(BaseModel):
    follow_up_actions: list[DownstreamFollowUpActionDescriptor] = Field(default_factory=list)
    operational_event_created: bool = False
    operational_event_id: str | None = None
    endpoint_health_hint: EndpointHealthHint | None = None
    summary: dict[str, object]


class DerivedWorkLineage(BaseModel):
    source_attempt_id: str | None = None
    source_command_id: str | None = None
    source_job_run_id: str | None = None
    source_correlation_id: str | None = None


class DerivedWorkRoutingResult(BaseModel):
    is_derived_work: bool
    action_type: DownstreamFollowUpActionType | None = None
    routing_category: DerivedWorkRoutingCategory | None = None
    lineage: DerivedWorkLineage | None = None
    summary: dict[str, object]


class DerivedWorkHandlerResult(BaseModel):
    handled: bool
    handler_category: DerivedWorkHandlerCategory | None = None
    pickup_category: DerivedWorkPickupCategory | None = None
    lineage: DerivedWorkLineage | None = None
    should_remain_pending: bool = True
    summary: dict[str, object]


class DerivedWorkCoordinationResult(BaseModel):
    coordinated: bool
    coordination_category: DerivedWorkCoordinationCategory | None = None
    handler_category: DerivedWorkHandlerCategory | None = None
    lineage: DerivedWorkLineage | None = None
    dispatch_ready: bool = True
    summary: dict[str, object]


class DerivedWorkDispatchRequestResult(BaseModel):
    dispatch_category: DerivedWorkDispatchCategory
    source_job_run_id: str
    lineage: DerivedWorkLineage | None = None
    derived_correlation_id: str | None = None
    dispatch_ready_metadata: dict[str, object]
    intended_path: str


class QueueEnqueueResult(BaseModel):
    enqueue_category: DerivedWorkEnqueueCategory
    dispatch_request_identity: str
    source_job_run_id: str
    lineage: DerivedWorkLineage | None = None
    derived_correlation_id: str | None = None
    adapter_receipt_id: str
    enqueue_status: QueueEnqueueStatus
    enqueue_metadata: dict[str, object]
    intended_path: str
