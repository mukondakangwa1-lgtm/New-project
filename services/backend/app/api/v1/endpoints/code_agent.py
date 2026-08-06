"""
Digital Campus - KUDOS Code Agent API
Autonomous code improvement with approval workflow.
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.code_agent import (
    analyze_codebase, generate_improvements, create_proposal, get_proposals,
    approve_proposal, reject_proposal, commit_approved_changes, push_changes,
    get_git_status, get_git_diff, get_auto_improvement_status, set_auto_improvement,
    set_repo_path,
)
from app.models import User

router = APIRouter()

# Auto-detect repo path
import os
set_repo_path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))


class ProposalCreate(BaseModel):
    title: str
    description: str
    category: str = "improvement"
    file_changes: list = []


# ──────────────────────────────────────────────
# CODEBASE ANALYSIS
# ──────────────────────────────────────────────

@router.get("/analyze")
def analyze(admin: User = Depends(require_admin)):
    """Analyze the codebase — find issues, stats, improvement opportunities."""
    analysis = analyze_codebase()
    suggestions = generate_improvements()
    return {
        "stats": analysis["stats"],
        "issues": analysis["issues"],
        "issue_count": analysis["issue_count"],
        "suggestions": suggestions,
    }


# ──────────────────────────────────────────────
# PROPOSAL WORKFLOW
# ──────────────────────────────────────────────

@router.get("/proposals")
def list_proposals(status: Optional[str] = None, admin: User = Depends(require_admin)):
    """List all change proposals. Filter: pending, approved, rejected, committed."""
    return {
        "proposals": get_proposals(status),
        "summary": {
            "pending": len([p for p in get_proposals() if p["status"] == "pending"]),
            "approved": len([p for p in get_proposals() if p["status"] == "approved"]),
            "rejected": len([p for p in get_proposals() if p["status"] == "rejected"]),
            "committed": len([p for p in get_proposals() if p["status"] == "committed"]),
        },
    }


@router.post("/proposals", status_code=201)
def createNewProposal(body: ProposalCreate, admin: User = Depends(require_admin)):
    """Create a new change proposal (superadmin only)."""
    proposal = create_proposal(body.title, body.description, body.category, body.file_changes)
    return {
        "id": proposal.id,
        "title": proposal.title,
        "status": proposal.status,
        "message": f"Proposal #{proposal.id} created: {proposal.title}",
    }


@router.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: int, admin: User = Depends(require_admin)):
    """Approve a change proposal (superadmin only)."""
    result = approve_proposal(proposal_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/proposals/{proposal_id}/reject")
def reject(proposal_id: int, admin: User = Depends(require_admin)):
    """Reject a change proposal (superadmin only)."""
    result = reject_proposal(proposal_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/proposals/{proposal_id}/commit")
def commit(proposal_id: int, admin: User = Depends(require_admin)):
    """Commit an approved proposal to git (superadmin only)."""
    result = commit_approved_changes(proposal_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/push")
def push(admin: User = Depends(require_admin)):
    """Push committed changes to remote (superadmin only)."""
    result = push_changes()
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ──────────────────────────────────────────────
# GIT OPERATIONS
# ──────────────────────────────────────────────

@router.get("/git/status")
def git_status(admin: User = Depends(require_admin)):
    """Get current git status."""
    return get_git_status()


@router.get("/git/diff")
def git_diff(admin: User = Depends(require_admin)):
    """Get current uncommitted changes."""
    return get_git_diff()


# ──────────────────────────────────────────────
# AUTO-IMPROVEMENT
# ──────────────────────────────────────────────

@router.get("/auto-improvement/status")
def auto_improvement_status(admin: User = Depends(require_admin)):
    """Get auto-improvement engine status."""
    return get_auto_improvement_status()


@router.post("/auto-improvement/toggle")
def toggle_auto_improvement(enable: bool = True, admin: User = Depends(require_admin)):
    """Enable or disable auto-improvement."""
    return set_auto_improvement(enable)


@router.post("/auto-improvement/generate")
def auto_generate_proposals(admin: User = Depends(require_admin)):
    """Generate improvement proposals from codebase analysis."""
    suggestions = generate_improvements()
    created = []
    for s in suggestions:
        proposal = create_proposal(s["title"], s["description"], s["category"], [{"file": f} for f in s.get("files", [])])
        created.append({"id": proposal.id, "title": proposal.title})
    return {
        "generated": len(created),
        "proposals": created,
        "message": f"Generated {len(created)} improvement proposals. Review and approve them to commit.",
    }
