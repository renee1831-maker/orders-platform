import logging
import re
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("app.access")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        # Se valida el ID entrante para evitar inyección en logs.
        request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else uuid4().hex
        started = perf_counter()

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        logger.info(
            "request_completed",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                }
            },
        )
        return response
