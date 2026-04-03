from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.auth.dependencies import require_permission
from app.modules.gis.schemas import GisLiteEntityListResponse
from app.modules.gis.service import list_gis_lite_entities
from app.modules.users.models import User

gis_lite_router = APIRouter(prefix="/gis-lite", tags=["gis-lite"])


@gis_lite_router.get("/entities", response_model=GisLiteEntityListResponse)
def list_gis_lite_entities_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    meter_id: UUID | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("meters.read")),
    __: User = Depends(require_permission("consumers.read")),
) -> GisLiteEntityListResponse:
    return list_gis_lite_entities(session, limit=limit, meter_id=meter_id)
