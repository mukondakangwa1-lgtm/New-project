"""
Digital Campus - Health Check Endpoint
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
