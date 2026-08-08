"""
Digital Campus Unified API — FastAPI Entry Point
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import (
    RequestLogMiddleware,
    configure_logging,
    get_request_id,
)
# Import all models so tables get created
from app.models import *  # noqa
from app.models_extended import *  # noqa

configure_logging()


class ShieldMiddleware(BaseHTTPMiddleware):
    """Middleware for intrusion detection, rate limiting, and performance tracking."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"

        # Check if IP is blocked
        try:
            from app.core.kudos_shield import is_blocked
            if is_blocked(client_ip):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. You have been temporarily blocked."},
                )
        except ImportError:
            pass

        # Process request
        response = await call_next(request)

        # Track performance, intrusion detection, and device fingerprinting
        duration_ms = (time.time() - start_time) * 1000
        try:
            from app.core.kudos_shield import track_request, track_performance
            track_request(client_ip, request.url.path, request.method, response.status_code)
            track_performance(duration_ms, is_error=response.status_code >= 500)
        except ImportError:
            pass

        # Fingerprint connecting devices
        try:
            from app.core.device_analyzer import fingerprint_request
            fingerprint_request({
                "ip": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
                "accept_language": request.headers.get("accept-language", ""),
                "accept_encoding": request.headers.get("accept-encoding", ""),
            })
        except ImportError:
            pass

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start runtime services without mutating production schemas."""
    if settings.AUTO_CREATE_TABLES:
        init_db()
    # Auto-activate shield
    try:
        from app.core.kudos_shield import start_shield
        start_shield()
    except Exception:
        pass
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Unified API for the Digital Campus platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Request logging (outermost) — adds X-Request-ID and per-request logs
app.add_middleware(RequestLogMiddleware)

# Shield middleware — intrusion detection, rate limiting, performance
app.add_middleware(ShieldMiddleware)

# CORS — configure explicit origins in production. The wildcard is useful
# only for local development and intentionally disables credentials there.
_cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all v1 routes under /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
        "ready": "/api/v1/health/ready",
        "shield": "active",
    }


# ---------- Global exception handlers ----------


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Uniform error envelope that always includes the request id.

    Registered on Starlette's HTTPException so router-level errors (404/405)
    and FastAPI's HTTPException subclass are both covered.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": get_request_id(),
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors()[:10],
            "request_id": get_request_id(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last resort — log the traceback, hide internals from the client."""
    import logging

    logging.getLogger("digital_campus").exception(
        "unhandled exception %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            # carried by the request-log middleware when we ran inside it
            "request_id": getattr(exc, "request_id", None) or get_request_id(),
        },
    )
