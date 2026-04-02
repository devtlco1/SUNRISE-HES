from collections.abc import Generator
from contextlib import asynccontextmanager, contextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import get_db_session
from app.core.logging import configure_logging
from app.db import models as db_models  # noqa: F401
from app.db.session import SessionLocal
from app.modules.auth.bootstrap import bootstrap_access_control
from app.modules.audit.middleware import request_context_middleware
from app.runtime.services import (
    evaluate_redis_transport_readiness,
    get_database_readiness_detail,
    get_platform_startup_readiness,
    initialize_platform_readiness_history,
    record_platform_startup_readiness_event,
    start_runtime_tcp_meter_ingress_listener,
    stop_runtime_tcp_meter_ingress_listener,
)

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@contextmanager
def _startup_db_session(app: FastAPI) -> Generator:
    override = app.dependency_overrides.get(get_db_session)
    if override is None:
        with SessionLocal() as session:
            yield session
        return

    session_dependency = override()
    session = next(session_dependency)
    try:
        yield session
    finally:
        try:
            next(session_dependency)
        except StopIteration:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    with _startup_db_session(app) as session:
        bootstrap_result = bootstrap_access_control(session)
    logger.info(
        "Access control bootstrap completed: permissions_seeded=%s roles_created=%s "
        "super_admin_created=%s super_admin_assigned=%s",
        bootstrap_result.permissions_created,
        bootstrap_result.roles_created,
        bootstrap_result.super_admin_created,
        bootstrap_result.super_admin_assigned,
    )
    initialize_platform_readiness_history(app)
    app.state.redis_transport_startup_readiness = evaluate_redis_transport_readiness(
        apply_startup_policy=True
    )
    app.state.database_startup_readiness = get_database_readiness_detail()
    record_platform_startup_readiness_event(app, get_platform_startup_readiness(app))
    start_runtime_tcp_meter_ingress_listener()
    try:
        yield
    finally:
        stop_runtime_tcp_meter_ingress_listener()


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(request_context_middleware)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {
        "service": settings.project_name,
        "company": settings.company_name,
        "status": "backend-foundation-ready",
    }
