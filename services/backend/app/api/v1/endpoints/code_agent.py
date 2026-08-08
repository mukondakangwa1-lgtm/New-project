"""
Digital Campus - KUDOS Code Agent API
Autonomous code improvement with approval workflow.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.deps import require_admin
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


def _proposal_edits(proposal_id: int) -> list | None:
    """Fetch an existing proposal's edit set (files_changed -> edits)."""
    try:
        proposals = get_proposals()
    except Exception:
        return None
    for p in proposals:
        if p["id"] == proposal_id and p.get("files_changed"):
            return [c for c in p["files_changed"] if isinstance(c, dict)]
    return None


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
def commit(proposal_id: int, approve: bool = False, admin: User = Depends(require_admin)):
    """Commit an approved proposal to git (allowlist staging only).

    ``approve`` acknowledges protected-branch rules (main/master/develop
    commits are refused without it). Pass approve=true on the task branch.
    """
    result = commit_approved_changes(proposal_id, approval=approve)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/push")
def push(approved: bool = False, admin: User = Depends(require_admin)):
    """Push committed changes to remote (requires explicit approval)."""
    result = push_changes(approved=approved)
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
# ARCHITECTURE INDEX
# ──────────────────────────────────────────────

@router.get("/architecture")
def architecture(force: bool = False, admin: User = Depends(require_admin)):
    """Get the architecture index — tree, modules, symbols, stats."""
    from app.core import archindex
    from app.core.code_agent import get_repo_path

    index = archindex.get_architecture_index(get_repo_path(), force=force)
    if "error" in index:
        raise HTTPException(404, index["error"])
    return {"summary": archindex.summarize(index), **index}


# ──────────────────────────────────────────────
# TASK RUNNER
# ──────────────────────────────────────────────

class TaskCreate(BaseModel):
    task_type: str = "run_command"
    command: str = ""
    workspace: Optional[str] = None
    repo_root: Optional[str] = None
    name: Optional[str] = None
    timeout: int = 120
    edits: Optional[list] = None
    proposal_id: Optional[int] = None
    wait: bool = True


@router.post("/tasks", status_code=201)
async def run_new_task(body: TaskCreate, admin: User = Depends(require_admin)):
    """Create and execute a task inside an isolated KUDOS workspace.

    With ``wait=true`` (default) the request blocks until the task finishes
    and returns the full result. With ``wait=false`` the task executes in the
    background and the response returns immediately with a ``task_id``; poll
    ``GET /tasks/{task_id}`` for progress (status: pending|running|done|failed).
    """
    import asyncio

    from anyio import to_thread
    from app.core import task_runner
    from app.core.task_runner import TaskRunnerError

    payload = {
        "command": body.command,
        "timeout": max(1, min(body.timeout, 600)),
    }
    if body.workspace:
        payload["workspace"] = body.workspace
    elif body.repo_root and body.name:
        payload["repo_root"] = body.repo_root
        payload["name"] = body.name
    if body.edits is not None:
        payload["edits"] = body.edits[:200]
    if body.proposal_id is not None:
        payload["proposal_id"] = body.proposal_id
        if body.edits is None:
            payload["edits"] = _proposal_edits(body.proposal_id)
    try:
        task = task_runner.create_task(body.task_type, payload)
        if not body.wait:
            asyncio.create_task(_background_run(task.id))
            return {
                "task_id": task.id,
                "status": "pending",
                "message": f"Task {task.id} queued — poll GET /tasks/{task.id}",
            }
        result = await to_thread.run_sync(task_runner.run_task, task.id)
    except TaskRunnerError as exc:
        raise HTTPException(400, str(exc))
    return result


async def _background_run(task_id: int) -> None:
    """Run a task off the event loop; settle the row on any unexpected
    exception so it never stays pending forever."""
    from anyio import to_thread
    from app.core import task_runner

    try:
        await to_thread.run_sync(task_runner.run_task, task_id)
    except Exception as exc:  # noqa: BLE001 — row must always be settled
        task_runner.fail_task(task_id, f"internal error: {exc}")


@router.get("/tasks")
def list_tasks(status: Optional[str] = None, limit: int = 50,
               admin: User = Depends(require_admin)):
    """List recent agent tasks from the persisted task store."""
    from app.core import task_runner

    return {"tasks": task_runner.list_tasks(status=status, limit=limit)}


@router.get("/tasks/logs")
def task_logs(limit: int = 50, workspace: Optional[str] = None,
              admin: User = Depends(require_admin)):
    """Recent sandbox operation logs (audit trail)."""
    from app.core import task_runner

    return {"logs": task_runner.list_logs(limit=limit, workspace=workspace)}


@router.get("/tasks/{task_id}")
def task_detail(task_id: int, admin: User = Depends(require_admin)):
    """Get one agent task with its result."""
    from app.core import task_runner

    task = task_runner.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


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
