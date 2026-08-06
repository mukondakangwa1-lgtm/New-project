"""
Digital Campus - KUDOS Shield API
Self-protection, intrusion detection, backup, performance monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.core.deps import require_admin
from app.core.kudos_shield import (
    start_shield, stop_shield, get_shield_status, get_shield_log,
    get_threat_log, get_blocked_ips, unblock_ip,
    update_baseline, track_request, track_performance,
    _create_backup, restore_backup, list_backups,
)
from app.models import User

router = APIRouter()


@router.get("/status")
def shield_status(admin: User = Depends(require_admin)):
    """Get shield status."""
    return get_shield_status()


@router.post("/activate")
def activate_shield(admin: User = Depends(require_admin)):
    """Activate the shield."""
    return start_shield()


@router.post("/deactivate")
def deactivate_shield(admin: User = Depends(require_admin)):
    """Deactivate the shield."""
    return stop_shield()


@router.get("/log")
def shield_log(limit: int = 50, admin: User = Depends(require_admin)):
    """Get shield activity log."""
    return {"log": get_shield_log(limit)}


@router.get("/threats")
def threats(limit: int = 50, admin: User = Depends(require_admin)):
    """Get threat log."""
    return {"threats": get_threat_log(limit)}


@router.get("/blocked")
def blocked_ips(admin: User = Depends(require_admin)):
    """Get blocked IPs."""
    return {"blocked": get_blocked_ips()}


@router.post("/unblock/{ip}")
def unblock(ip: str, admin: User = Depends(require_admin)):
    """Unblock an IP."""
    unblock_ip(ip)
    return {"status": "unblocked", "ip": ip}


@router.post("/integrity/update")
def update_integrity(admin: User = Depends(require_admin)):
    """Update file integrity baseline."""
    return update_baseline()


@router.post("/backup")
def create_backup(admin: User = Depends(require_admin)):
    """Create a manual backup."""
    return _create_backup()


@router.get("/backups")
def backups(admin: User = Depends(require_admin)):
    """List available backups."""
    return {"backups": list_backups()}


@router.post("/restore")
def restore(backup_file: str, admin: User = Depends(require_admin)):
    """Restore from a backup."""
    return restore_backup(backup_file)


@router.get("/performance")
def performance(admin: User = Depends(require_admin)):
    """Get performance statistics."""
    from app.core.kudos_shield import get_performance_stats
    return get_performance_stats()
