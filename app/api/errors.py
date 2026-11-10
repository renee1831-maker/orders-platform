import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import (
    ConcurrencyConflictError,
    DomainError,
    InvalidCursorError,
    InvalidOrderError,
    InvalidStatusTransitionError,
    OrderNotFoundError,
)

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    OrderNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidStatusTransitionError: status.HTTP_409_CONFLICT,
    ConcurrencyConflictError: status.HTTP_409_CONFLICT,
    InvalidCursorError: status.HTTP_400_BAD_REQUEST,
    InvalidOrderError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def _domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)  # noqa: S101 - registrado solo para DomainError
    status_code = _STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    details = None
    if isinstance(exc, InvalidStatusTransitionError):
        details = {"current": exc.current, "requested": exc.requested, "allowed": exc.allowed}
    return error_response(status_code, exc.code, exc.message, details)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    details = [
        {"field": ".".join(str(p) for p in err.get("loc", ())), "message": err.get("msg", "")}
        for err in exc.errors()
    ]
    return error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR",
        "La solicitud contiene datos inválidos.",
        details,
    )


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    return error_response(
        exc.status_code, "HTTP_ERROR", str(exc.detail), headers=getattr(exc, "headers", None)
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Nunca se filtra el detalle interno al cliente; queda en CloudWatch.
    logger.exception(
        "unhandled_error", extra={"extra_fields": {"path": request.url.path}}, exc_info=exc
    )
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Error interno del servidor."
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
