from fastapi import APIRouter

from app.api.v1.routes.health import router as health_router
from app.modules.accounts.api import accounts_router
from app.modules.auth.api import router as auth_router
from app.modules.commands.api import (
    command_templates_router,
    commands_router,
    internal_commands_router,
    meter_commands_router,
)
from app.modules.connectivity.api import (
    communication_endpoints_router,
    connectivity_credentials_router,
    meter_connectivity_router,
    protocol_association_profiles_router,
)
from app.modules.consumers.api import consumers_router
from app.modules.events.api import events_router, internal_meter_events_router, meter_events_router
from app.modules.gis.api import gis_lite_router
from app.modules.jobs.api import (
    command_control_router,
    internal_command_attempts_router,
    internal_job_runs_router,
    internal_scheduler_router,
    job_definitions_router,
    job_runs_router,
)
from app.modules.meters.api import (
    communication_profiles_router,
    firmware_versions_router,
    manufacturers_router,
    meter_models_router,
    meter_profiles_router,
    meters_router,
)
from app.modules.readings.api import (
    internal_meter_ingestion_router,
    load_profile_channels_router,
    meter_readings_router,
)
from app.modules.service_points.api import service_points_router
from app.modules.users.api import permissions_router, roles_router, users_router
from app.runtime.api import (
    internal_runtime_attempts_router,
    internal_runtime_job_runs_router,
    internal_runtime_platform_router,
    internal_runtime_queue_router,
    internal_runtime_router,
)

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(accounts_router)
api_router.include_router(auth_router)
api_router.include_router(command_templates_router)
api_router.include_router(meter_commands_router)
api_router.include_router(commands_router)
api_router.include_router(internal_commands_router)
api_router.include_router(command_control_router)
api_router.include_router(events_router)
api_router.include_router(gis_lite_router)
api_router.include_router(meter_events_router)
api_router.include_router(internal_meter_events_router)
api_router.include_router(communication_endpoints_router)
api_router.include_router(protocol_association_profiles_router)
api_router.include_router(connectivity_credentials_router)
api_router.include_router(meter_connectivity_router)
api_router.include_router(consumers_router)
api_router.include_router(job_definitions_router)
api_router.include_router(job_runs_router)
api_router.include_router(internal_job_runs_router)
api_router.include_router(internal_scheduler_router)
api_router.include_router(internal_command_attempts_router)
api_router.include_router(manufacturers_router)
api_router.include_router(meter_models_router)
api_router.include_router(firmware_versions_router)
api_router.include_router(communication_profiles_router)
api_router.include_router(meter_profiles_router)
api_router.include_router(meters_router)
api_router.include_router(meter_readings_router)
api_router.include_router(load_profile_channels_router)
api_router.include_router(internal_meter_ingestion_router)
api_router.include_router(service_points_router)
api_router.include_router(internal_runtime_router)
api_router.include_router(internal_runtime_attempts_router)
api_router.include_router(internal_runtime_job_runs_router)
api_router.include_router(internal_runtime_platform_router)
api_router.include_router(internal_runtime_queue_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
