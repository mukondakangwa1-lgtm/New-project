"""
Digital Campus - KUDOS Root Access & Identity
Superadmin-only root terminal, identity management, guidelines, self-improvement.
"""
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.kudos_identity import (
    add_guideline,
    delete_guideline,
    edit_guideline,
    get_guidelines,
    get_identity,
    get_improvement_log,
    get_knowledge_gaps,
    get_new_abilities,
    get_status_report,
    log_improvement,
    rename,
    set_guidelines,
    update_body_part,
    update_identity,
)
from app.core.paths import project_root
from app.models import User

router = APIRouter()

REPO_PATH = str(project_root(__file__))


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


@router.patch("/guidelines/{index}")
def edit_rule(index: int, new_text: str, admin: User = Depends(require_admin)):
    """Edit a single guideline by its 1-based number (as shown in the UI)."""
    try:
        return {"result": edit_guideline(index, new_text)}
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/guidelines/{index}")
def delete_rule(index: int, admin: User = Depends(require_admin)):
    """Delete a single guideline by its 1-based number (as shown in the UI)."""
    try:
        return {"result": delete_guideline(index)}
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc))


# ──────────────────────────────────────────────
# ROOT TERMINAL
# ──────────────────────────────────────────────

class RootCommand(BaseModel):
    command: str
    args: str = ""


@router.post("/exec")
def root_execute(body: RootCommand, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Execute a root command (superadmin only). Safe commands only."""
    cmd = body.command.lower().strip()
    args = body.args.strip()

    safe_commands = {
        "status": lambda: get_status_report(),
        "identity": lambda: get_identity(),
        "guidelines": lambda: _guidelines_command(args),
        "rule": lambda: _guidelines_command(args),
        "rules": lambda: _guidelines_command(args),
        "abilities": lambda: {"abilities": get_new_abilities()},
        "gaps": lambda: {"gaps": get_knowledge_gaps()},
        "log": lambda: {"log": get_improvement_log()},
        "tree": lambda: _get_file_tree(),
        "files": lambda: _list_files(args),
        "read": lambda: _read_file(args),
        "stats": lambda: _get_stats(),
        "governance": lambda: _governance_command(db, admin, args),
        "selfheal": lambda: _selfheal_command(db),
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


def _selfheal_command(db: Session) -> dict:
    """Self-heal plan shown in the terminal."""
    from app.core.kudos_governance import self_heal_plan
    return self_heal_plan(db)


def _governance_command(db: Session, admin: User, args: str) -> dict:
    """Check governance: identity, rotation, succession, or rotate the UID."""
    from app.core.kudos_governance import governance_status, rotate_uid, self_heal_bootstrap

    parts = args.split(" ", 1)
    sub = parts[0].lower() if args else ""
    if sub in ("rotate", "rotate-uid"):
        return {"rotated": rotate_uid(db, admin)}
    if sub in ("bootstrap", "script", "continuity"):
        return {"bootstrap": self_heal_bootstrap(db)}
    return governance_status(db)


def _guidelines_command(args: str) -> dict:
    """Manage KUDOS guidelines from the root terminal.

    Usage:
      guidelines                     → list all rules
      guidelines add <text>          → add a rule
      guidelines edit <n> <text>     → edit rule #n (1-based, as shown in the UI)
      guidelines delete <n>          → delete rule #n
      guidelines clear               → remove all rules
    """
    parts = args.split(" ", 1)
    sub = parts[0].lower() if args else ""
    rest = parts[1].strip() if len(parts) > 1 else ""

    if not sub:
        rules = get_guidelines()
        return {"guidelines": rules, "count": len(rules),
                "usage": "guidelines add|edit <n>|delete <n>|clear"}

    if sub == "add":
        if not rest:
            return {"error": "Usage: guidelines add <text>"}
        return {"result": add_guideline(rest)}

    if sub in ("edit", "delete"):
        idx_part, _, text = rest.partition(" ")
        try:
            index = int(idx_part)
        except ValueError:
            return {"error": f"Usage: guidelines {sub} <rule-number> [new text]"}

        def _index_error(exc: ValueError) -> dict:
            return {"error": str(exc)}

        try:
            if sub == "edit":
                if not text.strip():
                    return {"error": "Usage: guidelines edit <rule-number> <new text>"}
                return {"result": edit_guideline(index, text.strip())}
            return {"result": delete_guideline(index)}
        except ValueError as exc:
            return _index_error(exc)

    if sub == "clear":
        return {"result": set_guidelines([])}

    return {"error": f"Unknown guideline sub-command: {sub} (try add|edit|delete|clear)"}


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


# ──────────────────────────────────────────────
# GOVERNANCE & CONTINUITY
# ──────────────────────────────────────────────

@router.get("/governance")
def governance(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Rotating superadmin identity + transparent succession state."""
    from app.core.kudos_governance import governance_status
    return governance_status(db)


@router.post("/rotate-uid")
def rotate_uid(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Force an immediate rotation of the superadmin's unique ID."""
    from app.core.kudos_governance import rotate_uid as _rotate_uid
    return {"rotated": _rotate_uid(db, admin)}


@router.get("/continuity")
def continuity(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Everything KUDOS needs to rebuild anywhere + the host bootstrap script."""
    from app.core.kudos_governance import revival_bundle, self_heal_bootstrap
    return {
        "bundle": revival_bundle(db),
        "bootstrap": self_heal_bootstrap(db),
    }


@router.post("/self-heal")
def self_heal(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Plan (not execution — it runs on the host) to rebuild the whole stack."""
    from app.core.kudos_governance import self_heal_plan
    return self_heal_plan(db)
