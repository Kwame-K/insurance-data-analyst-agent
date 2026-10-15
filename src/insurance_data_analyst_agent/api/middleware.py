from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from insurance_data_analyst_agent.logging_config import (
    new_correlation_id,
    set_correlation_id,
)

logger = logging.getLogger(__name__)

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

CORRELATION_HEADER = "X-Correlation-ID"
REQUEST_HEADER = "X-Request-ID"


def _valid_or_none(value: str | None) -> str | None:
    if value and IDENTIFIER_PATTERN.match(value):
        return value
    return None


async def correlation_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Propagate correlation_id and request_id through the whole request."""
    correlation_id = (
        _valid_or_none(request.headers.get(CORRELATION_HEADER)) or new_correlation_id()
    )
    request_id = _valid_or_none(request.headers.get(REQUEST_HEADER))

    request.state.correlation_id = correlation_id
    request.state.request_id = request_id
    set_correlation_id(correlation_id)

    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000

    response.headers[CORRELATION_HEADER] = correlation_id
    if request_id:
        response.headers[REQUEST_HEADER] = request_id

    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )

    return response
