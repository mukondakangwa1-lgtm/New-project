"""
Digital Campus - KUDOS Auto-Learner API
Automated learning from all sources.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.deps import get_current_user, require_admin
from app.core.auto_learner import (
    get_auto_learner_status,
    start_auto_learner,
    stop_auto_learner,
    trigger_learning_cycle,
)
from app.models import User

router = APIRouter()


@router.get("/status")
def status(admin: User = Depends(require_admin)):
    """Get auto-learner status and statistics."""
    return get_auto_learner_status()


@router.post("/start")
def start(interval_minutes: int = 30, admin: User = Depends(require_admin)):
    """Start the auto-learner (learns every N minutes)."""
    return start_auto_learner(interval_minutes)


@router.post("/stop")
def stop(admin: User = Depends(require_admin)):
    """Stop the auto-learner."""
    return stop_auto_learner()


@router.post("/trigger")
def trigger(admin: User = Depends(require_admin)):
    """Manually trigger a single learning cycle now."""
    return trigger_learning_cycle()
