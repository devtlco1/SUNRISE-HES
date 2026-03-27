from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.modules.audit.context import (
    REQUEST_ID_HEADER,
    bind_request_context,
    create_request_context,
    reset_request_context,
)


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    context = create_request_context(request)
    request.state.request_audit_context = context
    token = bind_request_context(context)
    try:
        response = await call_next(request)
    finally:
        reset_request_context(token)

    response.headers[REQUEST_ID_HEADER] = context.request_id
    return response
