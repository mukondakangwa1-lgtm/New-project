"""
Digital Campus - KUDOS Root Access & Identity
Superadmin-only root terminal, identity management, guidelines, self-improvement.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.deps import require_admin
from app.core.kudos_identity import (
    get_identity, update_identity, rename, get_guidelines, set_guidelines,
    add_guideline, update_body_part, get_status_report, get_improvement_log,
    get_new_abilities, get_knowledge_gaps, log_improvement, log_new_ability,
)
from app.models import User

router = APIRouter()

REPO_PATH = str(Path(__file__).parent.parent.parent.parent)


# ──────────────────────────────────────────────
# IDENTITY
# ──────────────────────────────────────────────

@router.get("/identity")
def get_kudos_identity(admin: User = Depends(require_admin)):
    """Get KUDOS's full identity."""
    return get_identity()


@router.patch("/identity")
def update_kudos_identity(updates: dict, admin: User = Depends(require_admin)):
    """Update KUDOS's identity (name, personality, etc.)."""
    return update_identity(updates)


@router.post("/identity/rename")
def rename_kudos(new_name: str, admin: User = Depends(require_admin)):
    """Rename KUDOS."""
    return rename(new_name)


@router.patch("/body/{part}")
def update_body(part: str, updates: dict, admin: User = Depends(require_admin)):
    """Update a body part (brain, eyes, ears, mouth, hands, legs, heart, soul)."""
    return update_body_part(part, updates)


# ──────────────────────────────────────────────
# GUIDELINES
# ──────────────────────────────────────────────

@router.get("/guidelines")
def list_guidelines(admin: User = Depends(require_admin)):
    """Get all KUDOS guidelines."""
    return {"guidelines": get_guidelines()}


@router.put("/guidelines")
def replace_guidelines(guidelines: list[str], admin: User = Depends(require_admin)):
    """Replace all guidelines (superadmin only)."""
    return {"result": set_guidelines(guidelines)}


@router.post("/guidelines/add")
def add_rule(guideline: str, admin: User = Depends(require_admin)):
    """Add a single guideline."""
    return {"result": add_guideline(guideline)}


# ──────────────────────────────────────────────
# ROOT TERMINAL
# ──────────────────────────────────────────────

class RootCommand(BaseModel):
    command: str
    args: str = ""


@router.post("/root/exec")
def root_execute(body: RootCommand, admin: User = Depends(require_admin)):
    """Execute a root command (superadmin only). Safe commands only."""
    cmd = body.command.lower().strip()
    args = body.args.strip()

    safe_commands = {
        "status": lambda: get_status_report(),
        "identity": lambda: get_identity(),
        "guidelines": lambda: {"guidelines": get_guidelines()},
        "abilities": lambda: {"abilities": get_new_abilities()},
        "gaps": lambda: {"gaps": get_knowledge_gaps()},
        "log": lambda: {"log": get_improvement_log()},
        "tree": lambda: _get_file_tree(),
        "files": lambda: _list_files(args),
        "read": lambda: _read_file(args),
        "stats": lambda: _get_stats(),
        "help": lambda: {"commands": list(safe_commands.keys()), "description": "KUDOS root terminal"},
    }

    if cmd in safe_commands:
        try:
            result = safe_commands[cmd]()
            log_improvement("root_command", f"Executed: {cmd} {args}")
            return {"command": cmd, "result": result}
        except Exception as e:
            return {"command": cmd, "error": str(e)}

    return {"error": f"Unknown command: {cmd}. Type 'help' for available commands."}


def _get_file_tree() -> dict:
    """Get project file tree."""
    tree = []
    for root, dirs, files in os.walk(REPO_PATH):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "__pycache__", ".next")]
        level = root.replace(REPO_PATH, "").count(os.sep)
        if level > 3:
            continue
        indent = " " * 2 * level
        tree.append(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 2 * (level + 1)
        for f in files[:10]:
            tree.append(f"{subindent}{f}")
    return {"tree": "\n".join(tree[:100]), "total_files": len(tree)}


def _list_files(path: str = "") -> dict:
    """List files in a directory."""
    target = os.path.join(REPO_PATH, path) if path else REPO_PATH
    if not os.path.isdir(target):
        return {"error": f"Not a directory: {path}"}
    items = []
    for item in sorted(os.listdir(target)):
        if item.startswith("."):
            continue
        full = os.path.join(target, item)
        items.append({
            "name": item,
            "type": "dir" if os.path.isdir(full) else "file",
            "size": os.path.getsize(full) if os.path.isfile(full) else 0,
        })
    return {"path": path or ".", "items": items}


def _read_file(path: str) -> dict:
    """Read a file's content."""
    target = os.path.join(REPO_PATH, path)
    if not os.path.isfile(target):
        return {"error": f"File not found: {path}"}
    if os.path.getsize(target) > 50000:
        return {"error": "File too large (>50KB)"}
    try:
        with open(target, "r") as f:
            content = f.read()
        return {"path": path, "content": content, "lines": len(content.split("\n"))}
    except Exception as e:
        return {"error": str(e)}


def _get_stats() -> dict:
    """Get project statistics."""
    total_files = 0
    total_lines = 0
    file_types = {}
    for root, dirs, files in os.walk(os.path.join(REPO_PATH, "services", "backend")):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "__pycache__")]
        for f in files:
            if f.endswith(".py"):
                total_files += 1
                ext = f.rsplit(".", 1)[-1]
                file_types[ext] = file_types.get(ext, 0) + 1
                try:
                    with open(os.path.join(root, f)) as fh:
                        total_lines += len(fh.readlines())
                except:
                    pass
    for root, dirs, files in os.walk(os.path.join(REPO_PATH, "frontend", "pages")):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".next")]
        for f in files:
            if f.endswith((".tsx", ".ts", ".css")):
                total_files += 1
                ext = f.rsplit(".", 1)[-1]
                file_types[ext] = file_types.get(ext, 0) + 1
                try:
                    with open(os.path.join(root, f)) as fh:
                        total_lines += len(fh.readlines())
                except:
                    pass
    return {"files": total_files, "lines": total_lines, "by_type": file_types}


# ──────────────────────────────────────────────
# SELF-IMPROVEMENT
# ──────────────────────────────────────────────

@router.get("/status")
def full_status(admin: User = Depends(require_admin)):
    """Get full KUDOS status report."""
    return get_status_report()


@router.get("/improvements")
def improvements(limit: int = 50, admin: User = Depends(require_admin)):
    """Get improvement log."""
    return {"improvements": get_improvement_log(limit)}


@router.get("/abilities")
def abilities(limit: int = 50, admin: User = Depends(require_admin)):
    """Get newly learned abilities."""
    return {"abilities": get_new_abilities(limit)}


@router.get("/gaps")
def gaps(admin: User = Depends(require_admin)):
    """Get knowledge gaps."""
    return {"gaps": get_knowledge_gaps()}
