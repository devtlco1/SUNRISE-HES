from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db import models as db_models  # noqa: F401
from app.modules.audit.middleware import request_context_middleware

configure_logging(settings.log_level)

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
