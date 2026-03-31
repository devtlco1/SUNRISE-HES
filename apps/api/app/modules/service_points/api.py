import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.auth.dependencies import require_permission
from app.modules.service_points.schemas import (
    ServicePointDetailResponse,
    ServicePointListResponse,
)
from app.modules.service_points.service import (
    get_service_point_detail,
    list_service_points,
)
from app.modules.users.models import User

service_points_router = APIRouter(prefix="/service-points", tags=["service-points"])


@service_points_router.get("", response_model=ServicePointListResponse)
def list_service_points_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("meters.read")),
    __: User = Depends(require_permission("consumers.read")),
) -> ServicePointListResponse:
    return list_service_points(session, offset=offset, limit=limit, search=search)


@service_points_router.get("/{service_point_id}", response_model=ServicePointDetailResponse)
def get_service_point_detail_endpoint(
    service_point_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("meters.read")),
    __: User = Depends(require_permission("consumers.read")),
) -> ServicePointDetailResponse:
    return get_service_point_detail(session, service_point_id=service_point_id)
