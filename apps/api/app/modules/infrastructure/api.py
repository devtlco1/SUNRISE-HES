import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.auth.dependencies import require_permission
from app.modules.infrastructure.schemas import (
    TransformerSubstationDetailResponse,
    TransformerSubstationListResponse,
)
from app.modules.infrastructure.service import (
    get_transformer_substation_detail,
    list_transformer_substations,
)
from app.modules.users.models import User

infrastructure_router = APIRouter(
    prefix="/transformers-substations",
    tags=["transformers-substations"],
)


@infrastructure_router.get("", response_model=TransformerSubstationListResponse)
def list_transformer_substations_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("meters.read")),
    __: User = Depends(require_permission("consumers.read")),
) -> TransformerSubstationListResponse:
    return list_transformer_substations(session, offset=offset, limit=limit, search=search)


@infrastructure_router.get(
    "/{transformer_id}",
    response_model=TransformerSubstationDetailResponse,
)
def get_transformer_substation_detail_endpoint(
    transformer_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("meters.read")),
    __: User = Depends(require_permission("consumers.read")),
) -> TransformerSubstationDetailResponse:
    return get_transformer_substation_detail(session, transformer_id=transformer_id)
