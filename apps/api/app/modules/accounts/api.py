import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.modules.accounts.schemas import AccountDetailResponse, AccountListResponse
from app.modules.accounts.service import get_account_detail, list_accounts
from app.modules.auth.dependencies import require_permission
from app.modules.users.models import User

accounts_router = APIRouter(prefix="/accounts", tags=["accounts"])


@accounts_router.get("", response_model=AccountListResponse)
def list_accounts_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("consumers.read")),
    __: User = Depends(require_permission("meters.read")),
) -> AccountListResponse:
    return list_accounts(session, offset=offset, limit=limit, search=search)


@accounts_router.get("/{account_id}", response_model=AccountDetailResponse)
def get_account_detail_endpoint(
    account_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    _: User = Depends(require_permission("consumers.read")),
    __: User = Depends(require_permission("meters.read")),
) -> AccountDetailResponse:
    return get_account_detail(session, account_id=account_id)
