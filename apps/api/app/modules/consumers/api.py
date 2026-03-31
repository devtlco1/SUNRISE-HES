import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.auth.dependencies import require_permission
from app.modules.consumers.schemas import ConsumerDetailResponse, ConsumerListResponse
from app.modules.consumers.service import get_consumer_detail, list_consumers
from app.modules.users.models import User

consumers_router = APIRouter(prefix="/consumers", tags=["consumers"])


@consumers_router.get("", response_model=ConsumerListResponse)
def list_consumers_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("consumers.read")),
) -> ConsumerListResponse:
    return list_consumers(session, offset=offset, limit=limit, search=search)


@consumers_router.get("/{consumer_id}", response_model=ConsumerDetailResponse)
def get_consumer_detail_endpoint(
    consumer_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("consumers.read")),
) -> ConsumerDetailResponse:
    return get_consumer_detail(session, consumer_id)
