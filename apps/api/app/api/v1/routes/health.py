from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/platform")


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.project_name,
        "environment": settings.app_env,
    }
