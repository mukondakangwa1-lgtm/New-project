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
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.database import SessionLocal
from app.core.workspace import Workspace, WorkspaceError, WORKSPACES_DIR_NAME
from app.models import AgentTask, SandboxLog

KNOWN_TASK_TYPES = {"run_command", "quality_gate", "edit_apply"}


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


def _log(workspace: str | None, operation: str, command: str,
         status: str, output: str = "", exit_code: int | None = None,
         proposal_uuid: str | None = None) -> SandboxLog:
    entry = SandboxLog(
        workspace=workspace,
        operation=operation,
        command=command,
        status=status,
        output=output[:100000],
        exit_code=exit_code,
        proposal_uuid=proposal_uuid,
        finished_at=datetime.now(timezone.utc) if status != "queued" else None,
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
        task.started_at = datetime.now(timezone.utc)
        db.commit()
        ws = _workspace_from_payload(payload)
        if not ws.path.exists():
            raise WorkspaceError("Not a KUDOS workspace (path missing)")
        command = payload.get("command", "")
        if not command:
            raise TaskRunnerError("No command in payload")
        if any(seq in command for seq in ("..", ";", "&&", "||", "|", "$(", "`")):
            raise TaskRunnerError("Shell chaining / traversal is not allowed")
        parts = shlex.split(command)
        ws_root = Path(ws.path).resolve()
        for token in parts:
            if token.startswith("/") and not _is_inside(token, ws_root):
                raise TaskRunnerError("Path escapes the workspace sandbox")
    except (TaskRunnerError, WorkspaceError, json.JSONDecodeError) as exc:
        _fail(task_id, str(exc))
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
    finally:
        db.close()

    _log(ws.path.name, "command", command, "queued")
    try:
        result = ws.run(parts, timeout=int(payload.get("timeout", 120)))
    except WorkspaceError as exc:
        _log(ws.path.name, "command", command, "failed", output=str(exc), exit_code=-1,
             proposal_uuid=payload.get("proposal_uuid"))
        _fail(task_id, str(exc))
        return {"task_id": task_id, "status": "failed", "error": str(exc)}

    output = result.stdout or ""
    if result.returncode != 0:
        output = (output + "\n" + (result.stderr or "")).strip()
    _log(ws.path.name, "command", command, "done" if result.returncode == 0 else "failed",
         output=output, exit_code=result.returncode, proposal_uuid=payload.get("proposal_uuid"))

    outcome = {"exit_code": result.returncode, "output": output[:100000]}
    error = "" if result.returncode == 0 else f"exit code {result.returncode}"
    _finish(task_id, outcome, error)
    return {"task_id": task_id, "status": "done" if result.returncode == 0 else "failed",
            **outcome}


def _is_inside(path: str, ws_root: Path) -> bool:
    p = Path(path).resolve()
    return p == ws_root or ws_root in p.parents


def _fail(task_id: int, error: str):
    db = SessionLocal()
    try:
        task = db.query(AgentTask).get(task_id)
        if task:
            task.status = "failed"
            task.error = error[:5000]
            task.finished_at = datetime.now(timezone.utc)
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
            task.finished_at = datetime.now(timezone.utc)
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
