from fastapi import APIRouter

from app.core.config import settings
from app.runtime.contracts import PlatformReadinessResult
from app.runtime.services import get_platform_readiness

router = APIRouter(prefix="/platform")


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.project_name,
        "environment": settings.app_env,
    }


@router.get("/readiness", response_model=PlatformReadinessResult)
def readinesscheck() -> PlatformReadinessResult:
    return get_platform_readiness()
