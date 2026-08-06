"""
Digital Campus Unified API — FastAPI Entry Point
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import init_db
# Import all models so tables get created
from app.models import *  # noqa
from app.models_extended import *  # noqa


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
    """Create database tables on startup and activate shield."""
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

# Shield middleware — intrusion detection, rate limiting, performance
app.add_middleware(ShieldMiddleware)

# CORS — allow frontend dev server on any localhost port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
        "shield": "active",
    }
