"""
KUDOS Code Agent — Autonomous improvement engine
Analyzes the codebase, proposes improvements, waits for approval before committing.
Only the superadmin can approve changes.
"""
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
        import uuid as uuid_mod

        self.id = proposal_id
        self.uuid = str(uuid_mod.uuid4())
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
    """Create a new change proposal and mirror it to SQLite (Phase 4)."""
    import json

    from app.core.database import SessionLocal
    from app.models import SandboxProposal

    global _proposal_counter
    _proposal_counter += 1
    proposal = ChangeProposal(_proposal_counter, title, description, category)
    if file_changes:
        proposal.files_changed = file_changes
    _proposals.append(proposal)

    try:
        db = SessionLocal()
        try:
            row = SandboxProposal(
                uuid=proposal.uuid,
                title=title,
                description=description,
                category=category,
                status=proposal.status,
                source="code_agent",
                files_changed=json.dumps(file_changes or [], default=str),
                created_by=None,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception:
        # Persistence is best-effort; the in-memory flow still works.
        pass
    return proposal


def _sync_proposal_row(proposal: "ChangeProposal") -> None:
    """Best-effort mirror of an in-memory proposal into SQLite."""
    import json

    from app.core.database import SessionLocal
    from app.models import SandboxProposal

    try:
        db = SessionLocal()
        try:
            row = db.query(SandboxProposal).filter(SandboxProposal.uuid == proposal.uuid).first()
            if not row:
                row = SandboxProposal(uuid=proposal.uuid)
                db.add(row)
            row.title = proposal.title
            row.description = proposal.description
            row.category = proposal.category
            row.status = proposal.status
            row.files_changed = json.dumps(proposal.files_changed or [], default=str)
            row.commit_hash = proposal.commit_hash
            row.branch = proposal.git_branch or ""
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


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
            _sync_proposal_row(p)
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
            _sync_proposal_row(p)
            return {"status": "rejected", "id": p.id, "title": p.title}
    return {"error": "Proposal not found"}


# ──────────────────────────────────────────────
# GIT OPERATIONS (safe workflow via gitops.py)
# ──────────────────────────────────────────────

def _repo() -> str:
    return get_repo_path()


def get_git_status() -> dict:
    """Get current git status with branch protection info."""
    from app.core import gitops
    from pathlib import Path

    repo = Path(_repo())
    state = gitops.repo_state(repo)
    log = subprocess.run(["git", "log", "--oneline", "-5"], cwd=repo,
                         capture_output=True, text=True, timeout=30)
    diff_stat = subprocess.run(["git", "diff", "--stat"], cwd=repo,
                               capture_output=True, text=True, timeout=30)

    return {
        "branch": state.branch,
        "protected": state.protected,
        "status": "\n".join(
            [f"{'A ' if f in state.staged else '  '}{f}" for f in state.staged]
            + [f" {f}" for f in state.unstaged]
            + [f"?? {f}" for f in state.untracked]
        ).strip(),
        "staged": state.staged,
        "unstaged": state.unstaged,
        "untracked": state.untracked,
        "recent_commits": log.stdout.strip().split("\n") if log.stdout.strip() else [],
        "diff_stat": diff_stat.stdout.strip(),
    }


def commit_approved_changes(proposal_id: int, approval: bool = False) -> dict:
    """Commit changes for an approved proposal (allowlist staging).

    Only the files listed in the proposal are staged — never ``git add -A``.
    Protected branches require explicit approval.
    """
    from app.core import gitops
    from pathlib import Path

    proposal = None
    for p in _proposals:
        if p.id == proposal_id:
            proposal = p
            break

    if not proposal:
        return {"error": "Proposal not found"}
    if proposal.status != "approved":
        return {"error": f"Proposal must be approved first (current: {proposal.status})"}

    files = [c["file"] for c in proposal.files_changed if c.get("file")]
    if not files:
        return {"error": "Proposal lists no files to commit"}

    repo = Path(_repo())
    try:
        gitops.assert_task_branch(repo, approval=approval)
        commit_msg = f"kudos-improve: {proposal.title}\n\n{proposal.description}\n\nCategory: {proposal.category}\nApproved by: superadmin"
        result = gitops.commit(repo, commit_msg, files, repo_root=repo)
    except gitops.GitOpsError as exc:
        return {"error": str(exc)}

    proposal.commit_hash = result["committed"]
    proposal.git_branch = result["branch"]
    proposal.status = "committed"
    _sync_proposal_row(proposal)
    return {
        "status": "committed",
        "commit_hash": proposal.commit_hash,
        "branch": result["branch"],
        "message": f"Committed: {proposal.title}",
    }


def push_changes(approved: bool = False) -> dict:
    """Push committed changes to remote (requires approval, no force)."""
    from app.core import gitops
    from pathlib import Path

    try:
        result = gitops.push(Path(_repo()), approved=approved)
    except gitops.GitOpsError as exc:
        return {"error": str(exc)}
    return {"status": "pushed", "branch": result["branch"]}


def get_git_diff() -> dict:
    """Get staged and unstaged diffs separately."""
    from app.core import gitops
    from pathlib import Path

    return gitops.diff_sections(Path(_repo()))


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
