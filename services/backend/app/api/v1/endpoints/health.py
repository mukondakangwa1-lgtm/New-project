"""
Digital Campus - Health, Readiness and Metrics Endpoints
"""
import os
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.deps import require_admin
from app.core.logging import REQUEST_COUNTER
from app.schemas import HealthCheck

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
def health_check():
    return HealthCheck(
        status="healthy",
        version=settings.APP_VERSION,
        message=f"Welcome to {settings.APP_NAME}",
    )


def _db_latency_ms() -> float:
    """Return DB round-trip latency in ms, or -1.0 when the DB is unreachable."""
    start = time.perf_counter()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        return -1.0
    return (time.perf_counter() - start) * 1000


def _redis_ready() -> bool:
    """Ping Redis; fails soft when Redis is not configured or unreachable."""
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        return bool(client.ping())
    except Exception:
        return False


def _system_stats() -> dict:
    """Lightweight host stats using only the standard library."""
    stats = {"cpu_count": os.cpu_count(), "load_avg": None, "mem_mb": {}, "disk_free_mb": None}
    try:
        stats["load_avg"] = os.getloadavg()
    except (AttributeError, OSError):
        pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for line in lines[:3]:
            if ":" in line:
                key, value = line.split(":", 1)
                stats["mem_mb"][key] = int(value.split()[0]) // 1024
    except OSError:
        pass
    try:
        stat = os.statvfs(".")
        stats["disk_free_mb"] = (stat.f_bavail * stat.f_frsize) // (1024 * 1024)
    except OSError:
        pass
    return stats


@router.get("/health/ready")
def readiness_check():
    """Readiness probe — DB is required, Redis/storage degrade the status."""
    db_ms = _db_latency_ms()
    db_ready = db_ms >= 0
    redis_ready = _redis_ready()
    from app.core import storage

    storage_status = storage.status()

    return JSONResponse(
        status_code=200 if db_ready else 503,
        content={
            "status": "ready" if db_ready else "unavailable",
            "checks": {
                "database": {"ready": db_ready, "latency_ms": round(db_ms, 2)},
                "redis": {
                    "ready": redis_ready,
                    "mode": "ready" if redis_ready else "degraded",
                },
                "storage": storage_status,
            },
        },
    )


@router.get("/admin/metrics", dependencies=[Depends(require_admin)])
def metrics():
    """Superadmin-only system and request metrics (no external tooling)."""
    from app.core import kudos_shield, storage

    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "system": _system_stats(),
        "database": {"latency_ms": round(_db_latency_ms(), 2)},
        "redis": {"ready": _redis_ready()},
        "storage": storage.status(),
        "requests": REQUEST_COUNTER,
        "shield": {
            "blocked_ips": len(kudos_shield.get_blocked_ips()),
            "performance": kudos_shield._performance_stats,
            "threat_log_count": len(kudos_shield.get_threat_log(limit=1000)),
        },
    }