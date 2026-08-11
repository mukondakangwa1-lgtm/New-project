"""
Task runner — executes agent tasks in sandbox workspaces and persists every
operation (SandboxLog) plus the task result (AgentTask) to SQLite.

Design rules:
- tasks are dispatched to isolated workspace roots (see workspace.py); a task
  with no workspace is refused (no arbitrary host commands).
- each run is bounded by rlimits (CPU/AS/FSIZE) and a timeout via
  workspace.run().
- everything is append-only logged in kudos_sandbox_logs.
"""

import json
import re
import shlex
from datetime import UTC, datetime
from pathlib import Path

from app.core.database import SessionLocal
from app.core.workspace import WORKSPACES_DIR_NAME, Workspace, WorkspaceError
from app.models import AgentTask, SandboxLog

KNOWN_TASK_TYPES = {"run_command", "quality_gate", "edit_apply"}

# Shells expand env vars / ~ / globs inside a -c payload, so a static path
# scan cannot see what they would open. Refuse shell code-execution outright.
_SHELL_NAMES = {"sh", "bash", "dash", "zsh", "ksh", "csh", "tcsh", "fish"}

# Absolute paths anywhere in the raw command string (even nested inside a
# `-c` payload or function args) must stay inside the workspace.
_ABS_PATH_RE = re.compile(r"(?:^|[^\w/])(/[^\s'\"]+)")


class TaskRunnerError(Exception):
    """Raised for invalid task requests."""


def _workspace_from_payload(payload: dict) -> Workspace:
    """Build a Workspace from {repo_root, name} or {workspace} (path)."""
    if payload.get("repo_root") and payload.get("name"):
        return Workspace(payload["repo_root"], payload["name"])
    ws_path = payload.get("workspace")
    if not ws_path:
        raise TaskRunnerError("A workspace is required; host-wide commands are refused")
    p = Path(ws_path).resolve()
    if p.parent.name != WORKSPACES_DIR_NAME:
        raise TaskRunnerError("Not a KUDOS workspace path")
    return Workspace(p.parent.parent, p.name)


def _log(
    workspace: str | None,
    operation: str,
    command: str,
    status: str,
    output: str = "",
    exit_code: int | None = None,
    proposal_uuid: str | None = None,
) -> SandboxLog:
    entry = SandboxLog(
        workspace=workspace,
        operation=operation,
        command=command,
        status=status,
        output=output[:100000],
        exit_code=exit_code,
        proposal_uuid=proposal_uuid,
        finished_at=datetime.now(UTC) if status != "queued" else None,
    )
    db = SessionLocal()
    try:
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    finally:
        db.close()


def create_task(task_type: str, payload: dict, created_by: int | None = None) -> AgentTask:
    """Persist a new AgentTask row and return it."""
    if task_type not in KNOWN_TASK_TYPES:
        raise TaskRunnerError(f"Unknown task type: {task_type}")
    _workspace_from_payload(payload)  # validate early
    db = SessionLocal()
    try:
        task = AgentTask(
            task_type=task_type,
            payload=json.dumps(payload),
            status="pending",
            created_by=created_by,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


def run_task(task_id: int) -> dict:
    """Execute a pending task and persist the outcome. Returns result dict."""
    db = SessionLocal()
    try:
        task = db.query(AgentTask).get(task_id)
        if not task:
            raise TaskRunnerError(f"Task {task_id} not found")
        if task.status == "running":
            raise TaskRunnerError(f"Task {task_id} already running")
        payload = json.loads(task.payload or "{}")
        task.status = "running"
        task.started_at = datetime.now(UTC)
        db.commit()
        ws = _workspace_from_payload(payload)
        if not ws.path.exists():
            raise WorkspaceError("Not a KUDOS workspace (path missing)")
        if task.task_type == "edit_apply":
            edits = payload.get("edits")
            if not isinstance(edits, list) or not edits:
                raise TaskRunnerError("edit_apply requires an edits list")
        else:
            command = payload.get("command", "")
            if not command:
                raise TaskRunnerError("No command in payload")
            parts, error = _validate_command(command, Path(ws.path).resolve())
            if error:
                raise TaskRunnerError(error)
    except (TaskRunnerError, WorkspaceError, json.JSONDecodeError) as exc:
        _fail(task_id, str(exc))
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
    finally:
        db.close()

    if task.task_type == "edit_apply":
        return _run_edits(task, ws, edits, payload.get("proposal_uuid"))

    _log(ws.path.name, "command", command, "queued")
    try:
        result = ws.run(parts, timeout=int(payload.get("timeout", 120)))
    except WorkspaceError as exc:
        _log(
            ws.path.name,
            "command",
            command,
            "failed",
            output=str(exc),
            exit_code=-1,
            proposal_uuid=payload.get("proposal_uuid"),
        )
        _fail(task_id, str(exc))
        return {"task_id": task_id, "status": "failed", "error": str(exc)}

    output = result.stdout or ""
    if result.returncode != 0:
        output = (output + "\n" + (result.stderr or "")).strip()
    _log(
        ws.path.name,
        "command",
        command,
        "done" if result.returncode == 0 else "failed",
        output=output,
        exit_code=result.returncode,
        proposal_uuid=payload.get("proposal_uuid"),
    )

    outcome = {"exit_code": result.returncode, "output": output[:100000]}
    error = "" if result.returncode == 0 else f"exit code {result.returncode}"
    _finish(task_id, outcome, error)
    return {"task_id": task_id, "status": "done" if result.returncode == 0 else "failed", **outcome}


def _is_inside(path: str, ws_root: Path) -> bool:
    p = Path(path).resolve()
    return p == ws_root or ws_root in p.parents


def _mask_quoted(command: str) -> str:
    """Blank out quoted sections so shell-level separator checks do not fire
    on code that merely lives inside an argument string."""
    out: list[str] = []
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if c in "'\"":
            j = i + 1
            while j < n and command[j] != c:
                if command[j] == "\\":
                    j += 1
                j += 1
            out.append(" " * (j - i + 1))
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _validate_command(command: str, ws_root: Path) -> tuple[list[str], str | None]:
    """Static validation of a sandbox command string.

    Returns ``(parts, error)``; ``error`` is set when the command must be
    refused. Layers, in order:
    - shell chaining / command substitution strings (outside quotes);
    - empty argv (whitespace-only strings);
    - absolute paths found anywhere in the raw string (even inside a ``-c``
      payload) that resolve outside the workspace;
    - argv tokens that are absolute paths outside the workspace;
    - shell ``-c`` code execution (env/~ expansion cannot be audited).
    """
    if any(seq in _mask_quoted(command) for seq in ("..", ";", "&&", "||", "|", "$(", "`")):
        return [], "Shell chaining / traversal is not allowed"
    parts = shlex.split(command)
    if not parts:
        return [], "Empty command"
    for match in _ABS_PATH_RE.findall(command):
        if not _is_inside(match, ws_root):
            return parts, "Path escapes the workspace sandbox"
    for token in parts:
        if token.startswith("/") and not _is_inside(token, ws_root):
            return parts, "Path escapes the workspace sandbox"
    if any(token in _SHELL_NAMES for token in parts) and "-c" in parts:
        return parts, "Shell -c execution is not allowed"
    return parts, None


ALLOWED_EDIT_ACTIONS = {"create", "replace", "append", "insert"}


def _run_edits(task: "AgentTask", ws: "Workspace", edits: list, proposal_uuid: str | None = None) -> dict:
    """Apply a guarded edit set inside the workspace.

    Every edit path goes through pathguard.resolve_inside, so ``..``
    traversal, symlink escapes, system paths and protected names (credentials,
    keys, .git) are refused. Each edit resolves atomically on its own file.
    """
    from app.core.pathguard import PathError, resolve_inside

    applied, refusals = [], []
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            refusals.append({"index": i, "error": "edit must be an object"})
            continue
        relpath = edit.get("path")
        action = (edit.get("action") or "replace").lower()
        if not relpath or action not in ALLOWED_EDIT_ACTIONS:
            refusals.append(
                {
                    "index": i,
                    "error": f"edit needs a path and action in create|replace|append|insert (got action={action!r})",
                }
            )
            continue
        try:
            target = resolve_inside(ws.path, str(relpath), allow_missing=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = edit.get("content", edit.get("content_preview", ""))
            if action == "create":
                if target.exists():
                    refusals.append({"index": i, "path": relpath, "error": "file already exists"})
                    continue
                target.write_text(content)
            elif action == "replace":
                target.write_text(content)
            elif action == "append":
                with open(target, "a") as fh:
                    fh.write(content if content.endswith("\n") else content + "\n")
            elif action == "insert":
                line = int(edit.get("line") or 0)
                text = target.read_text() if target.exists() else ""
                lines = text.splitlines(keepends=True)
                lines.insert(min(max(line, 0), len(lines)), content + "\n")
                target.write_text("".join(lines))
        except (PathError, OSError, ValueError) as exc:
            refusals.append({"index": i, "path": relpath, "error": str(exc)})
            continue
        applied.append({"index": i, "path": str(target), "action": action})

    outcome = {
        "applied": len(applied),
        "refused": len(refusals),
        "files": [a["path"] for a in applied],
        "refusals": refusals[:50],
    }
    error = ""
    status = "done"
    if not applied and refusals:
        error = f"All {len(refusals)} edits refused"
        status = "failed"
    elif refusals:
        first = refusals[0]
        first_ref = first.get("path", f"edit #{first['index']}")
        error = f"{len(refusals)} of {len(edits)} edits refused (first: {first_ref}: {first['error']})"
        status = "failed"

    _log(
        ws.path.name,
        "edit_apply",
        f"{len(edits)} edits ({', '.join(sorted({e.get('action', 'replace') for e in edits}))})",
        status if not error else "partial",
        output=json.dumps({"applied": applied, "refusals": refusals[:50]}),
        exit_code=0 if status == "done" else -1,
        proposal_uuid=proposal_uuid,
    )
    _finish(task.id, outcome, error)
    return {"task_id": task.id, "status": status, "error": error, **outcome}


def fail_task(task_id: int, error: str) -> None:
    """Public wrapper for _fail — used to settle rows when a background
    execution path crashes outside the normal run_task flow."""
    _fail(task_id, error)


def _fail(task_id: int, error: str):
    db = SessionLocal()
    try:
        task = db.query(AgentTask).get(task_id)
        if task:
            task.status = "failed"
            task.error = error[:5000]
            task.finished_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()


def _finish(task_id: int, outcome: dict, error: str = ""):
    db = SessionLocal()
    try:
        task = db.query(AgentTask).get(task_id)
        if task:
            task.status = "done" if not error else "failed"
            task.result = json.dumps(outcome)
            task.error = error[:5000] if error else ""
            task.finished_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()


def get_task(task_id: int) -> dict | None:
    db = SessionLocal()
    try:
        task = db.query(AgentTask).get(task_id)
        if not task:
            return None
        return {
            "id": task.id,
            "task_type": task.task_type,
            "payload": json.loads(task.payload or "{}"),
            "status": task.status,
            "result": json.loads(task.result or "{}"),
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        }
    finally:
        db.close()


def list_tasks(status: str | None = None, limit: int = 50) -> list[dict]:
    """List recent agent tasks, newest first."""
    db = SessionLocal()
    try:
        q = db.query(AgentTask)
        if status:
            q = q.filter(AgentTask.status == status)
        q = q.order_by(AgentTask.id.desc()).limit(min(limit, 200))
        return [
            {
                "id": t.id,
                "task_type": t.task_type,
                "status": t.status,
                "result": json.loads(t.result or "{}"),
                "error": t.error,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            }
            for t in q.all()
        ]
    finally:
        db.close()


def list_logs(limit: int = 100, workspace: str | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        q = db.query(SandboxLog)
        if workspace:
            q = q.filter(SandboxLog.workspace == workspace)
        q = q.order_by(SandboxLog.id.desc()).limit(min(limit, 500))
        return [
            {
                "id": e.id,
                "workspace": e.workspace,
                "operation": e.operation,
                "command": e.command,
                "status": e.status,
                "exit_code": e.exit_code,
                "output": (e.output or "")[:5000],
                "proposal_uuid": e.proposal_uuid,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in q.all()
        ]
    finally:
        db.close()
