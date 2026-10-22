from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from insurance_data_analyst_agent.api.schemas import (
    ErrorDetail,
    ErrorResponse,
)
from insurance_data_analyst_agent.logging_config import get_correlation_id
from insurance_data_analyst_agent.services.router import (
    UnsupportedQuestionError,
)

logger = logging.getLogger(__name__)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", get_correlation_id())
    body = ErrorResponse(
        correlation_id=correlation_id,
        request_id=getattr(request.state, "request_id", None),
        error=ErrorDetail(code=code, message=message, details=details),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Correlation-ID": correlation_id},
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    validation_exc = cast(RequestValidationError, exc)
    details = [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
        for e in validation_exc.errors()
    ]
    return _error_response(
        request, 422, "validation_error", "Request validation failed.", details
    )


async def unsupported_question_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return _error_response(request, 422, "unsupported_question", str(exc))


async def data_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Data source unavailable")
    return _error_response(
        request, 503, "data_unavailable", "Data source is unavailable."
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    return _error_response(
        request, http_exc.status_code, "http_error", str(http_exc.detail)
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unexpected error")
    return _error_response(request, 500, "internal_error", "Internal server error.")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the uniform error contract to a FastAPI application."""
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(UnsupportedQuestionError, unsupported_question_handler)
    app.add_exception_handler(FileNotFoundError, data_unavailable_handler)
    app.add_exception_handler(OperationalError, data_unavailable_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
