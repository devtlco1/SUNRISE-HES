from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db import models as db_models  # noqa: F401
from app.modules.audit.middleware import request_context_middleware
from app.runtime.services import (
    evaluate_redis_transport_readiness,
    get_database_readiness_detail,
    get_platform_startup_readiness,
    initialize_platform_readiness_history,
    record_platform_startup_readiness_event,
)

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_platform_readiness_history(app)
    app.state.redis_transport_startup_readiness = evaluate_redis_transport_readiness(
        apply_startup_policy=True
    )
    app.state.database_startup_readiness = get_database_readiness_detail()
    record_platform_startup_readiness_event(app, get_platform_startup_readiness(app))
    yield


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
