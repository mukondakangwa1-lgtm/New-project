"""
Digital Campus - Health Check Endpoint
Now includes DB type/status so frontend knows which DB is active.
"""
from fastapi import APIRouter
from app.schemas import HealthCheck
from app.core.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
def health_check():
    return HealthCheck(
        status="healthy",
        version=settings.APP_VERSION,
        message=f"Welcome to {settings.APP_NAME}",
    )


@router.get("/health/db")
def db_health():
    """Detailed DB health — tells which DB is connected (Postgres or SQLite)."""
    try:
        from app.core.db_manager import test_connection
        return test_connection()
    except Exception as e:
        return {"ok": False, "error": str(e), "type": "Unknown"}


@router.get("/health/db-info")
def db_info():
    """Light DB info (no connection test) — fast."""
    try:
        from app.core.db_manager import get_db_info
        return get_db_info()
    except Exception as e:
        return {"error": str(e)}
