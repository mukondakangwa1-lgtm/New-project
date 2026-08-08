"""Structured logging with per-request correlation IDs.

Provides:
- ``configure_logging`` to install a single handler with a request-id filter;
- ``RequestLogMiddleware`` to assign an ``X-Request-ID`` per request, log each
  request with method/path/status/duration, and keep lightweight counters for
  the metrics endpoint.
"""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

_logger = logging.getLogger("digital_campus")

REQUEST_COUNTER = {"total": 0, "errors": 0, "by_status": {}}


def get_request_id() -> str:
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Install a single, consistently formatted handler on the root logger."""
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Our middleware logs every request; silence uvicorn's duplicate access log.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    for noisy in ("httpx", "httpcore", "sqlalchemy.engine", "passlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log one line per request and propagate an X-Request-ID header."""

    async def dispatch(self, request: "Request", call_next: Any) -> "Response":
        request_id = uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            REQUEST_COUNTER["total"] += 1
            REQUEST_COUNTER["errors"] += 1
            # The exception re-raises past this middleware (Shield, then the
            # ServerErrorMiddleware invokes the 500 handler outside our scope),
            # so carry the request id on the exception itself.
            exc.request_id = request_id  # type: ignore[attr-defined]
            _logger.exception(
                "unhandled error %s %s", request.method, request.url.path
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = (time.perf_counter() - start) * 1000
        REQUEST_COUNTER["total"] += 1
        REQUEST_COUNTER["by_status"][response.status_code] = (
            REQUEST_COUNTER["by_status"].get(response.status_code, 0) + 1
        )
        if response.status_code >= 500:
            REQUEST_COUNTER["errors"] += 1

        response.headers["X-Request-ID"] = request_id
        _logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response