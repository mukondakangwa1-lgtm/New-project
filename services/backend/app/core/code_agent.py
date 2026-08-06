"""
KUDOS Code Agent — Autonomous improvement engine
Analyzes the codebase, proposes improvements, waits for approval before committing.
Only the superadmin can approve changes.
"""
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────
# CHANGE PROPOSAL SYSTEM
# ──────────────────────────────────────────────

class ChangeProposal:
    """A proposed change to the codebase."""
    
    def __init__(self, proposal_id: int, title: str, description: str, category: str):
        self.id = proposal_id
        self.title = title
        self.description = description
        self.category = category  # feature, fix, improvement, security, performance
        self.files_changed: list[dict] = []  # [{path, action, content_preview}]
        self.status = "pending"  # pending, approved, rejected, committed
        self.created_at = datetime.now(timezone.utc)
        self.reviewed_at: Optional[datetime] = None
        self.commit_hash: Optional[str] = None
        self.git_branch: Optional[str] = None


# In-memory proposal store
_proposals: list[ChangeProposal] = []
_proposal_counter = 0
_auto_improvement_active = False
_repo_path = ""


def set_repo_path(path: str):
    """Set the repository path for git operations."""
    global _repo_path
    _repo_path = path


def get_repo_path() -> str:
    """Get the repository path."""
    global _repo_path
    if not _repo_path:
        # Auto-detect from current file location
        _repo_path = str(Path(__file__).parent.parent.parent.parent)
    return _repo_path


# ──────────────────────────────────────────────
# CODEBASE ANALYSIS
# ──────────────────────────────────────────────

def analyze_codebase() -> dict:
    """Analyze the codebase and find improvement opportunities."""
    repo = get_repo_path()
    issues = []
    stats = {"files": 0, "lines": 0, "functions": 0, "classes": 0}

    # Scan Python files
    for root, dirs, files in os.walk(os.path.join(repo, "services", "backend")):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", "node_modules", ".git")]
        for f in files:
            if not f.endswith(".py"):
                continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, "r") as fh:
                    content = fh.read()
                    lines = content.split("\n")
                    stats["files"] += 1
                    stats["lines"] += len(lines)
                    stats["functions"] += len(re.findall(r"^def ", content, re.MULTILINE))
                    stats["classes"] += len(re.findall(r"^class ", content, re.MULTILINE))

                    rel_path = os.path.relpath(filepath, repo)

                    # Check for issues
                    if "TODO" in content or "FIXME" in content:
                        for i, line in enumerate(lines):
                            if "TODO" in line or "FIXME" in line:
                                issues.append({
                                    "type": "todo",
                                    "file": rel_path,
                                    "line": i + 1,
                                    "text": line.strip()[:100],
                                })

                    # Check for long functions
                    func_starts = [i for i, l in enumerate(lines) if re.match(r"^def ", l)]
                    for start in func_starts:
                        # Find end of function
                        end = start + 1
                        while end < len(lines) and (lines[end].startswith("    ") or lines[end].strip() == ""):
                            end += 1
                        if end - start > 100:
                            issues.append({
                                "type": "long_function",
                                "file": rel_path,
                                "line": start + 1,
                                "text": f"Function is {end - start} lines (consider splitting)",
                            })

                    # Check for missing docstrings
                    for i, line in enumerate(lines):
                        if re.match(r"^class ", line) or re.match(r"^def ", line):
                            if i + 1 < len(lines) and '"""' not in lines[i + 1]:
                                issues.append({
                                    "type": "missing_docstring",
                                    "file": rel_path,
                                    "line": i + 1,
                                    "text": line.strip()[:60],
                                })

                    # Check for hardcoded values
                    for i, line in enumerate(lines):
                        if re.search(r'["\']localhost:\d+["\']', line):
                            issues.append({
                                "type": "hardcoded",
                                "file": rel_path,
                                "line": i + 1,
                                "text": line.strip()[:80],
                            })
            except Exception:
                continue

    # Scan frontend files
    for root, dirs, files in os.walk(os.path.join(repo, "frontend", "pages")):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", "node_modules", ".git")]
        for f in files:
            if not f.endswith((".tsx", ".ts", ".js")):
                continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, "r") as fh:
                    content = fh.read()
                    lines = content.split("\n")
                    stats["files"] += 1
                    stats["lines"] += len(lines)

                    rel_path = os.path.relpath(filepath, repo)

                    # Check for TODO/FIXME
                    for i, line in enumerate(lines):
                        if "TODO" in line or "FIXME" in line:
                            issues.append({
                                "type": "todo",
                                "file": rel_path,
                                "line": i + 1,
                                "text": line.strip()[:100],
                            })

                    # Check for console.log left in
                    for i, line in enumerate(lines):
                        if "console.log" in line and "debug" not in line.lower():
                            issues.append({
                                "type": "debug_code",
                                "file": rel_path,
                                "line": i + 1,
                                "text": line.strip()[:80],
                            })
            except Exception:
                continue

    return {
        "stats": stats,
        "issues": issues[:50],
        "issue_count": len(issues),
    }


# ──────────────────────────────────────────────
# IMPROVEMENT GENERATION
# ──────────────────────────────────────────────

def generate_improvements() -> list[dict]:
    """Generate improvement proposals based on codebase analysis."""
    analysis = analyze_codebase()
    suggestions = []

    # Group issues by type
    issue_types = {}
    for issue in analysis["issues"]:
        t = issue["type"]
        if t not in issue_types:
            issue_types[t] = []
        issue_types[t].append(issue)

    # Generate suggestions
    if "missing_docstring" in issue_types:
        count = len(issue_types["missing_docstring"])
        files = set(i["file"] for i in issue_types["missing_docstring"])
        suggestions.append({
            "title": f"Add docstrings to {count} functions/classes",
            "description": f"Missing docstrings in {len(files)} files. Adding docstrings improves code readability and auto-generated documentation.",
            "category": "improvement",
            "impact": "medium",
            "files": list(files)[:10],
            "auto_fixable": True,
        })

    if "long_function" in issue_types:
        suggestions.append({
            "title": f"Refactor {len(issue_types['long_function'])} long functions",
            "description": "Functions over 100 lines should be split into smaller, more focused functions.",
            "category": "improvement",
            "impact": "high",
            "files": list(set(i["file"] for i in issue_types["long_function"])),
            "auto_fixable": False,
        })

    if "todo" in issue_types:
        suggestions.append({
            "title": f"Address {len(issue_types['todo'])} TODO/FIXME items",
            "description": "Unfinished work items that should be completed or removed.",
            "category": "fix",
            "impact": "medium",
            "files": list(set(i["file"] for i in issue_types["todo"])),
            "auto_fixable": False,
        })

    if "debug_code" in issue_types:
        suggestions.append({
            "title": f"Remove {len(issue_types['debug_code'])} console.log statements",
            "description": "Debug logging left in production code.",
            "category": "cleanup",
            "impact": "low",
            "files": list(set(i["file"] for i in issue_types["debug_code"])),
            "auto_fixable": True,
        })

    if "hardcoded" in issue_types:
        suggestions.append({
            "title": f"Extract {len(issue_types['hardcoded'])} hardcoded values",
            "description": "Hardcoded URLs/ports should be moved to environment variables or config.",
            "category": "improvement",
            "impact": "medium",
            "files": list(set(i["file"] for i in issue_types["hardcoded"])),
            "auto_fixable": False,
        })

    # General suggestions
    suggestions.append({
        "title": "Add API rate limiting",
        "description": "Protect endpoints from abuse by adding rate limiting middleware.",
        "category": "security",
        "impact": "high",
        "files": ["services/backend/app/main.py"],
        "auto_fixable": True,
    })

    suggestions.append({
        "title": "Add database connection pooling",
        "description": "Use connection pooling for better database performance under load.",
        "category": "performance",
        "impact": "medium",
        "files": ["services/backend/app/core/database.py"],
        "auto_fixable": True,
    })

    suggestions.append({
        "title": "Add input validation middleware",
        "description": "Add request validation and sanitization middleware for security.",
        "category": "security",
        "impact": "high",
        "files": ["services/backend/app/main.py"],
        "auto_fixable": True,
    })

    suggestions.append({
        "title": "Add health check endpoint improvements",
        "description": "Add database connectivity check, memory usage, and uptime to health endpoint.",
        "category": "improvement",
        "impact": "low",
        "files": ["services/backend/app/api/v1/endpoints/health.py"],
        "auto_fixable": True,
    })

    return suggestions


# ──────────────────────────────────────────────
# PROPOSAL MANAGEMENT
# ──────────────────────────────────────────────

def create_proposal(title: str, description: str, category: str, file_changes: list[dict] = None) -> ChangeProposal:
    """Create a new change proposal."""
    global _proposal_counter
    _proposal_counter += 1
    proposal = ChangeProposal(_proposal_counter, title, description, category)
    if file_changes:
        proposal.files_changed = file_changes
    _proposals.append(proposal)
    return proposal


def get_proposals(status: Optional[str] = None) -> list[dict]:
    """Get all proposals, optionally filtered by status."""
    results = []
    for p in _proposals:
        if status and p.status != status:
            continue
        results.append({
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "category": p.category,
            "status": p.status,
            "files_changed": p.files_changed,
            "created_at": p.created_at.isoformat(),
            "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
            "commit_hash": p.commit_hash,
            "git_branch": p.git_branch,
        })
    return results


def approve_proposal(proposal_id: int) -> dict:
    """Approve a proposal — the change will be committed."""
    for p in _proposals:
        if p.id == proposal_id:
            if p.status != "pending":
                return {"error": f"Proposal is already {p.status}"}
            p.status = "approved"
            p.reviewed_at = datetime.now(timezone.utc)
            return {"status": "approved", "id": p.id, "title": p.title}
    return {"error": "Proposal not found"}


def reject_proposal(proposal_id: int) -> dict:
    """Reject a proposal."""
    for p in _proposals:
        if p.id == proposal_id:
            if p.status != "pending":
                return {"error": f"Proposal is already {p.status}"}
            p.status = "rejected"
            p.reviewed_at = datetime.now(timezone.utc)
            return {"status": "rejected", "id": p.id, "title": p.title}
    return {"error": "Proposal not found"}


# ──────────────────────────────────────────────
# GIT OPERATIONS
# ──────────────────────────────────────────────

def _run_git(args: list[str]) -> tuple[int, str]:
    """Run a git command and return (returncode, output)."""
    repo = get_repo_path()
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def get_git_status() -> dict:
    """Get current git status."""
    _, branch = _run_git(["branch", "--show-current"])
    _, status = _run_git(["status", "--short"])
    _, log = _run_git(["log", "--oneline", "-5"])
    _, diff = _run_git(["diff", "--stat"])

    return {
        "branch": branch.strip(),
        "status": status.strip(),
        "recent_commits": log.strip().split("\n") if log.strip() else [],
        "diff_stat": diff.strip(),
    }


def commit_approved_changes(proposal_id: int) -> dict:
    """Commit changes for an approved proposal."""
    proposal = None
    for p in _proposals:
        if p.id == proposal_id:
            proposal = p
            break

    if not proposal:
        return {"error": "Proposal not found"}
    if proposal.status != "approved":
        return {"error": f"Proposal must be approved first (current: {proposal.status})"}

    # Stage and commit
    rc, output = _run_git(["add", "-A"])
    if rc != 0:
        return {"error": f"Git add failed: {output}"}

    commit_msg = f"kudos-improve: {proposal.title}\n\n{proposal.description}\n\nCategory: {proposal.category}\nApproved by: superadmin"
    rc, output = _run_git(["commit", "-m", commit_msg])
    if rc != 0:
        return {"error": f"Git commit failed: {output}"}

    # Get commit hash
    _, hash_output = _run_git(["rev-parse", "HEAD"])
    proposal.commit_hash = hash_output.strip()
    proposal.status = "committed"

    return {
        "status": "committed",
        "commit_hash": proposal.commit_hash,
        "message": f"Committed: {proposal.title}",
    }


def push_changes() -> dict:
    """Push committed changes to remote."""
    _, branch = _run_git(["branch", "--show-current"])
    branch = branch.strip()
    rc, output = _run_git(["push", "origin", branch])
    if rc != 0:
        return {"error": f"Push failed: {output}"}
    return {"status": "pushed", "branch": branch}


def get_git_diff() -> dict:
    """Get current uncommitted changes."""
    _, diff = _run_git(["diff"])
    _, staged = _run_git(["diff", "--cached"])
    return {
        "unstaged": diff.strip(),
        "staged": staged.strip(),
    }


# ──────────────────────────────────────────────
# AUTO-IMPROVEMENT ENGINE
# ──────────────────────────────────────────────

def get_auto_improvement_status() -> dict:
    """Get status of auto-improvement engine."""
    return {
        "active": _auto_improvement_active,
        "proposals_pending": len([p for p in _proposals if p.status == "pending"]),
        "proposals_approved": len([p for p in _proposals if p.status == "approved"]),
        "proposals_committed": len([p for p in _proposals if p.status == "committed"]),
    }


def set_auto_improvement(active: bool) -> dict:
    """Enable or disable auto-improvement."""
    global _auto_improvement_active
    _auto_improvement_active = active
    return {"active": active}
