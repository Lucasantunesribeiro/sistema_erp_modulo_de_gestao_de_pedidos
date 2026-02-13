import uuid
from contextvars import ContextVar
from typing import Callable

import structlog
from django.http import HttpRequest, HttpResponse

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

logger = structlog.get_logger()


class CorrelationIdMiddleware:
    """Middleware that extracts or generates a correlation ID for each request.

    Reads X-Request-ID header from the incoming request. If absent,
    generates a new UUID4. The ID is stored in a ContextVar so structlog
    processors can inject it into every log line, and is returned to the
    client via the X-Request-ID response header.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        cid = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        correlation_id_var.set(cid)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=cid)

        logger.info(
            "request_started",
            method=request.method,
            path=request.get_full_path(),
        )

        response = self.get_response(request)

        logger.info(
            "request_finished",
            method=request.method,
            path=request.get_full_path(),
            status_code=response.status_code,
        )

        response["X-Request-ID"] = cid
        return response
