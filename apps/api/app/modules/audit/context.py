from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, replace
import ipaddress
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"


@dataclass(frozen=True)
class RequestAuditContext:
    request_id: str
    method: str
    path: str
    ip_address: str | None
    user_agent: str | None
    actor_user_id: UUID | None = None


_request_context: ContextVar[RequestAuditContext | None] = ContextVar("request_audit_context", default=None)


def create_request_context(request: Request) -> RequestAuditContext:
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = None
    if forwarded_for:
        candidate = forwarded_for.split(",")[0].strip()
        ip_address = _validate_ip_address(candidate)
    elif request.client is not None:
        ip_address = _validate_ip_address(request.client.host)

    return RequestAuditContext(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )


def _validate_ip_address(candidate: str | None) -> str | None:
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def bind_request_context(context: RequestAuditContext) -> Any:
    return _request_context.set(context)


def reset_request_context(token: Any) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestAuditContext | None:
    return _request_context.get()


def attach_actor_to_context(actor_user_id: UUID) -> None:
    context = get_request_context()
    if context is None:
        return
    _request_context.set(replace(context, actor_user_id=actor_user_id))
