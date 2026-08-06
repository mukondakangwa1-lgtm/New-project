"""
KUDOS Guardian API — Secure superadmin channel, integrity checks, self-improvement.
Only superadmin can access these endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.kudos_guardian import (
    KudosSecureChannel,
    KudosSelfImprover,
    secure_channel,
    self_improver,
    verify_integrity,
    update_hashes_after_admin_change,
    save_integrity_hashes,
    KUDOS_PROTECTED_PATHS,
)
from app.models import User

router = APIRouter()


# ──────────────────────────────────────────────
# INTEGRITY ENDPOINTS
# ──────────────────────────────────────────────


@router.get("/integrity")
def check_integrity(admin: User = Depends(require_admin)):
    """Verify all KUDOS files are intact (superadmin only)."""
    return verify_integrity()


@router.post("/integrity/update")
def update_hashes(admin: User = Depends(require_admin)):
    """Update integrity hashes after authorized changes (superadmin only)."""
    result = update_hashes_after_admin_change()
    return {
        "status": "updated",
        "message": "Integrity hashes updated for all protected files",
        "files": list(result.get("hashes", {}).keys()),
        "updated_by": admin.email,
    }


@router.get("/integrity/files")
def list_protected_files(admin: User = Depends(require_admin)):
    """List all protected KUDOS files (superadmin only)."""
    return {
        "protected_files": KUDOS_PROTECTED_PATHS,
        "count": len(KUDOS_PROTECTED_PATHS),
        "description": "These files are integrity-checked and only modifiable by superadmin",
    }


# ──────────────────────────────────────────────
# SECURE CHANNEL ENDPOINTS
# ──────────────────────────────────────────────


@router.post("/channel/open")
def open_secure_channel(admin: User = Depends(require_admin)):
    """Open a secure communication channel with KUDOS (superadmin only)."""
    key = secure_channel.initialize(admin.id)
    return {
        "status": "connected",
        "message": "🔒 Secure channel established with KUDOS",
        "session_key": key[:16] + "...",
        "admin": admin.email,
    }


@router.post("/channel/command")
def execute_command(
    command: str,
    params: dict = {},
    admin: User = Depends(require_admin),
):
    """Execute a command on KUDOS through the secure channel (superadmin only)."""
    result = secure_channel.execute_command(admin.id, True, command, params)
    return result


@router.get("/channel/audit")
def get_audit_log(
    limit: int = 50,
    admin: User = Depends(require_admin),
):
    """Get KUDOS command audit log (superadmin only)."""
    log = secure_channel.get_audit_log(limit)
    return {
        "entries": log,
        "total": len(log),
    }


# ──────────────────────────────────────────────
# SELF-IMPROVEMENT ENDPOINTS
# ──────────────────────────────────────────────


@router.get("/improvement/report")
def improvement_report(admin: User = Depends(require_admin)):
    """Get KUDOS self-improvement report (superadmin only)."""
    return self_improver.get_improvement_report()


@router.post("/improvement/feedback")
def submit_feedback(
    question: str,
    rating: int,
    comment: str = "",
    admin: User = Depends(require_admin),
):
    """Submit feedback on KUDOS response quality (superadmin only)."""
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    self_improver.log_feedback(admin.id, question, rating, comment)
    return {
        "status": "recorded",
        "message": "Feedback logged — KUDOS will use this to improve",
    }


@router.get("/system/status")
def system_status(admin: User = Depends(require_admin)):
    """Get full KUDOS system status (superadmin only)."""
    integrity = verify_integrity()
    improvement = self_improver.get_improvement_report()

    return {
        "integrity": integrity,
        "improvement": {
            "total_questions": improvement["total_questions"],
            "answer_rate": improvement["answer_rate"],
            "average_rating": improvement["average_rating"],
            "recommendation": improvement["recommendation"],
        },
        "protected_files": len(KUDOS_PROTECTED_PATHS),
        "secure_channel": "active" if secure_channel._access_key else "inactive",
    }
