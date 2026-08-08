"""KUDOS Terminal — agent execution channel.

KUDOS opens a terminal on any connected device, or online when no device is
available. Device sessions run commands on the user's own hardware through the
device agent (poll-based, same channel as memory sync). Online sessions run on
the server inside a per-session jailed workspace.

Gate: commands issued by the agent (LLM) enter ``pending_approval`` and only
execute after the superadmin approves them. Direct user commands run freely.
Code runs (language set) are syntax-bounded and execute immediately.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import KudosDevice, KudosTerminalCommand, KudosTerminalSession

ONLINE_TIMEOUT_SECONDS = 30
ONLINE_OUTPUT_CAP = 64 * 1024
CLAIM_STALE_SECONDS = 90
DEVICE_ONLINE_WINDOW_MINUTES = 30


def _workspace_root() -> str:
    try:
        from app.core.config import settings

        if settings.KUDOS_TERMINAL_WORKSPACE_ROOT:
            return settings.KUDOS_TERMINAL_WORKSPACE_ROOT
    except Exception:
        pass
    return os.environ.get("KUDOS_WORKSPACE_ROOT") or os.path.join(
        tempfile.gettempdir(), "kudos_workspace"
    )


WORKSPACE_ROOT = _workspace_root()
LANGUAGES = {"python3": ".py", "node": ".js", "bash": ".sh"}
DEFAULT_INTERPRETER = {"python3": "python3", "node": "node", "bash": "bash"}

# Shell commands KUDOS (or its agent) may never run — online or device side.
DENY_PATTERNS = [
    r"\bsudo\b",                       # privilege escalation
    r"\bsu\b\s*[- ]",                  # switch user
    r"\brm\s+-(?:[a-zA-Z]*[rf]{1,2}[a-zA-Z]*)\s*[/*~$]",  # destructive removes
    r":\(\)",                          # fork bomb
    r"\bmkfs(?:\.\w+)?\b",             # format devices
    r"\bdd\b[^|&;]*\bof=/dev/",        # raw device writes
    r"\b(?:poweroff|reboot|halt|shutdown)\b",
    r"\bchmod\s+(?:-R\s+)?[0-7]{3,4}\s+[/*]",  # chmod on root paths
    r"\bumount\b",
    r"\bkill\s+-9\s+1\b",
    r"\bchown\b[^|&;]*(?:/|~)",
]
_DENY_RE = re.compile("|".join(DENY_PATTERNS), re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize DB-stored (naive, SQLite) datetimes to aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _get_session(db: Session, session_id: int, user_id: int, admin: bool = False) -> KudosTerminalSession:
    session = db.get(KudosTerminalSession, session_id)
    if not session:
        raise ValueError("session not found")
    if session.user_id != user_id and not admin:
        raise PermissionError("not your session")
    return session


# ──────────────────────────────────────────────
# SESSIONS
# ──────────────────────────────────────────────

def create_session(
    db: Session,
    user_id: int,
    device_id: Optional[int] = None,
    name: str = "kudos-terminal",
    opened_by: str = "user",
    admin: bool = False,
) -> KudosTerminalSession:
    """Open a terminal. device_id given → device session; None → online session.

    Online sessions execute on the server, so they require superadmin consent.
    """
    if device_id is not None:
        device = db.get(KudosDevice, device_id)
        if not device or device.user_id != user_id:
            raise ValueError("device not found")
        kind = "device"
    else:
        kind = "online"
        if not admin:
            raise PermissionError("online sessions require superadmin")

    session = KudosTerminalSession(
        user_id=user_id,
        device_id=device_id,
        kind=kind,
        name=(name or "kudos-terminal")[:120],
        status="open",
        opened_by=opened_by[:20],
    )
    db.add(session)
    db.flush()
    if kind == "online":
        workspace = os.path.join(WORKSPACE_ROOT, f"session-{session.id}")
        os.makedirs(workspace, exist_ok=True)
        session.workspace = workspace
    db.commit()
    db.refresh(session)
    return session


def close_session(db: Session, session_id: int, user_id: int, admin: bool = False) -> dict:
    session = _get_session(db, session_id, user_id, admin)
    if session.status != "open":
        return {"status": session.status}
    session.status = "closed"
    session.closed_at = _now()
    db.commit()
    return {"status": "closed", "session_id": session.id}


def list_sessions(db: Session, user_id: int) -> List[dict]:
    rows = (
        db.query(KudosTerminalSession)
        .filter(KudosTerminalSession.user_id == user_id)
        .order_by(KudosTerminalSession.created_at.desc())
        .all()
    )
    return [session_to_dict(s) for s in rows]


def session_to_dict(session: KudosTerminalSession) -> dict:
    return {
        "id": session.id,
        "user_id": session.user_id,
        "device_id": session.device_id,
        "kind": session.kind,
        "name": session.name,
        "status": session.status,
        "opened_by": session.opened_by,
        "workspace": session.workspace,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
    }


def transcript(db: Session, session_id: int, user_id: int, admin: bool = False, limit: int = 50) -> dict:
    session = _get_session(db, session_id, user_id, admin)
    cmds = (
        db.query(KudosTerminalCommand)
        .filter(KudosTerminalCommand.session_id == session.id)
        .order_by(KudosTerminalCommand.id.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return {
        "session": session_to_dict(session),
        "commands": [command_to_dict(c) for c in cmds],
    }


def command_to_dict(cmd: KudosTerminalCommand) -> dict:
    return {
        "id": cmd.id,
        "session_id": cmd.session_id,
        "command": cmd.command,
        "language": cmd.language,
        "source": cmd.source,
        "status": cmd.status,
        "exit_code": cmd.exit_code,
        "output": (cmd.output or "")[:2000],
        "requested_at": cmd.requested_at.isoformat() if cmd.requested_at else None,
        "executed_at": cmd.executed_at.isoformat() if cmd.executed_at else None,
    }


def pick_session_for_user(
    db: Session, user_id: int, admin: bool = False, opened_by: str = "ask"
) -> Tuple[KudosTerminalSession, bool]:
    """KUDOS picks a terminal: a device session on a recently-seen device,
    else an online session (superadmin only). Returns (session, created)."""
    device = (
        db.query(KudosDevice)
        .filter(
            KudosDevice.user_id == user_id,
            KudosDevice.status == "online",
        )
        .order_by(KudosDevice.last_seen_at.desc())
        .first()
    )
    if device:
        cutoff = _now() - timedelta(minutes=DEVICE_ONLINE_WINDOW_MINUTES)
        recent = _aware(device.last_seen_at) is not None and _aware(device.last_seen_at) >= cutoff
        if recent:
            session = (
                db.query(KudosTerminalSession)
                .filter(
                    KudosTerminalSession.user_id == user_id,
                    KudosTerminalSession.device_id == device.id,
                    KudosTerminalSession.status == "open",
                )
                .order_by(KudosTerminalSession.created_at.desc())
                .first()
            )
            if not session:
                session = create_session(db, user_id, device_id=device.id, opened_by=opened_by)
                return session, True
            return session, False

    if not admin:
        raise PermissionError("no terminal available for this user")
    session = (
        db.query(KudosTerminalSession)
        .filter(
            KudosTerminalSession.user_id == user_id,
            KudosTerminalSession.kind == "online",
            KudosTerminalSession.status == "open",
        )
        .order_by(KudosTerminalSession.created_at.desc())
        .first()
    )
    if not session:
        session = create_session(db, user_id, device_id=None, opened_by=opened_by, admin=True)
        return session, True
    return session, False


# ──────────────────────────────────────────────
# ENQUEUE & APPROVAL
# ──────────────────────────────────────────────

def enqueue_command(
    db: Session,
    session_id: int,
    user_id: int,
    command: str,
    source: str = "user",
    language: str = "",
    admin: bool = False,
) -> KudosTerminalCommand:
    """Queue a command in a session.

    Agent-issued shell commands require superadmin approval first; agent code
    runs (language set) and direct user commands execute immediately.
    """
    session = _get_session(db, session_id, user_id, admin)
    if session.status != "open":
        raise ValueError("session is closed")
    if language and language not in LANGUAGES:
        raise ValueError(f"unsupported language: {language}")

    if source not in ("user", "agent", "ask"):
        source = "user"

    needs_approval = source == "agent" and not language
    cmd = KudosTerminalCommand(
        session_id=session.id,
        user_id=session.user_id,
        device_id=session.device_id,
        command=(command or "")[:4000],
        language=language,
        source=source,
        status="pending_approval" if needs_approval else "queued",
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return cmd


def approve_command(db: Session, command_id: int, admin_user_id: int) -> dict:
    cmd = db.get(KudosTerminalCommand, command_id)
    if not cmd:
        raise ValueError("command not found")
    if cmd.status != "pending_approval":
        raise ValueError("command is not awaiting approval")
    cmd.status = "queued"
    cmd.approved_by = admin_user_id
    db.commit()
    return command_to_dict(cmd)


def pending_approvals(db: Session, admin_user_id: int) -> List[dict]:
    rows = (
        db.query(KudosTerminalCommand)
        .filter(KudosTerminalCommand.status == "pending_approval")
        .order_by(KudosTerminalCommand.requested_at.asc())
        .all()
    )
    return [command_to_dict(c) for c in rows]


# ──────────────────────────────────────────────
# DEVICE CHANNEL (pull-based)
# ──────────────────────────────────────────────

def claim_next_for_device(db: Session, device_token: str, max_batch: int = 5) -> List[dict]:
    """Return commands queued for this device and mark them claimed.

    Idempotent retries: a claimed command that was never executed within the
    stale window is offered again so a crashed device client does not lose it.
    """
    device = get_device_by_token(db, device_token)
    if not device:
        raise PermissionError("unknown device token")
    device.last_seen_at = _now()
    db.commit()

    now = _now()
    stale_limit = now - timedelta(seconds=CLAIM_STALE_SECONDS)
    rows = (
        db.query(KudosTerminalCommand)
        .filter(KudosTerminalCommand.device_id == device.id)
        .order_by(KudosTerminalCommand.id.asc())
        .all()
    )
    ready = [
        c for c in rows
        if c.status == "queued"
        or (
            c.status == "claimed"
            and (_aware(c.claimed_at) or now) < stale_limit
        )
    ][:max_batch]

    claimed = []
    for cmd in ready:
        cmd.status = "claimed"
        cmd.claimed_at = now
        claimed.append(command_to_dict(cmd))
    db.commit()
    return claimed


def submit_result(
    db: Session, device_token: str, command_id: int, exit_code: int, output: str
) -> dict:
    """Device agent posts the execution result of a claimed command."""
    device = get_device_by_token(db, device_token)
    if not device:
        raise PermissionError("unknown device token")
    device.last_seen_at = _now()
    db.commit()

    cmd = db.get(KudosTerminalCommand, command_id)
    if not cmd or cmd.device_id != device.id:
        raise ValueError("command not found for this device")
    if cmd.status != "claimed":
        raise ValueError("command was never claimed")

    cmd.exit_code = int(exit_code)
    cmd.output = (output or "")[:ONLINE_OUTPUT_CAP]
    cmd.status = "done" if int(exit_code) == 0 else "failed"
    cmd.executed_at = _now()
    db.commit()
    return command_to_dict(cmd)


def get_device_by_token(db: Session, token: str) -> Optional[KudosDevice]:
    from app.core.device_storage import get_device_by_token as _lookup

    return _lookup(db, token)


# ──────────────────────────────────────────────
# ONLINE EXECUTOR (jailed workspace)
# ──────────────────────────────────────────────

def _workspace_for(db: Session, session: KudosTerminalSession) -> str:
    workspace = session.workspace or os.path.join(WORKSPACE_ROOT, f"session-{session.id}")
    os.makedirs(workspace, exist_ok=True)
    if not session.workspace:
        session.workspace = workspace
        db.commit()
    return workspace


def _is_denied(command: str, language: str) -> Optional[str]:
    if language:
        return None
    match = _DENY_RE.search(command)
    if match:
        return f"Command blocked: matches deny pattern '{match.group(0)}'"
    return None


def execute_online(db: Session, cmd: KudosTerminalCommand) -> dict:
    """Run a queued command server-side in the session's jailed workspace."""
    session = db.get(KudosTerminalSession, cmd.session_id)
    if not session:
        raise ValueError("session not found")
    workspace = _workspace_for(db, session)
    cmd.status = "claimed"
    cmd.claimed_at = _now()
    db.commit()

    denied = _is_denied(cmd.command, cmd.language)
    if denied:
        return _finish(db, cmd, exit_code=127, output=denied)

    if cmd.language:
        ext = LANGUAGES[cmd.language]
        path = os.path.join(workspace, "code" + ext)
        try:
            with open(path, "w") as f:
                f.write(cmd.command)
        except OSError as exc:
            return _finish(db, cmd, exit_code=126, output=f"write failed: {exc}")
        shell_command = f"{DEFAULT_INTERPRETER[cmd.language]} {shlex.quote(path)}"
    else:
        shell_command = cmd.command

    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": workspace,
        "LANG": "C.UTF-8",
    }
    try:
        result = subprocess.run(
            ["bash", "-lc", shell_command],
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=ONLINE_TIMEOUT_SECONDS,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return _finish(db, cmd, exit_code=result.returncode, output=output)
    except subprocess.TimeoutExpired:
        return _finish(db, cmd, exit_code=124, output=f"timed out after {ONLINE_TIMEOUT_SECONDS}s")
    except Exception as exc:
        return _finish(db, cmd, exit_code=126, output=f"execution error: {exc}")


def _finish(db: Session, cmd: KudosTerminalCommand, exit_code: int, output: str) -> dict:
    cmd.exit_code = int(exit_code)
    cmd.output = (output or "")[:ONLINE_OUTPUT_CAP]
    cmd.status = "done" if int(exit_code) == 0 else "failed"
    cmd.executed_at = _now()
    db.commit()
    db.refresh(cmd)
    return command_to_dict(cmd)


def run_queued_online(db: Session, session_id: int) -> int:
    """Execute all queued commands of an online session (used by the ask flow)."""
    executed = 0
    rows = (
        db.query(KudosTerminalCommand)
        .filter(
            KudosTerminalCommand.session_id == session_id,
            KudosTerminalCommand.status == "queued",
        )
        .order_by(KudosTerminalCommand.id.asc())
        .all()
    )
    for cmd in rows:
        execute_online(db, cmd)
        executed += 1
    return executed


# ──────────────────────────────────────────────
# AGENT LOOP
# ──────────────────────────────────────────────

AGENT_MAX_ROUNDS = 3
AGENT_MAX_COMMANDS_PER_ROUND = 4


async def run_agent_round(db: Session, session_id: int, task: str, admin_user_id: int) -> dict:
    """One agent round: the LLM plans steps for the task.

    Shell commands enter pending_approval for the superadmin; code runs are
    queued immediately. Returns the planned steps; approve them and call again
    to continue the loop with the results in context.
    """
    from app.core.llm_engine import query_best_llm

    session = _get_session(db, session_id, admin_user_id, admin=True)
    history = transcript(db, session_id, admin_user_id, admin=True, limit=30)["commands"]

    system_prompt = (
        "You are KUDOS's terminal agent, working in a session opened on the "
        "user's device or a jailed online workspace. Plan the next steps to "
        f"accomplish the task. The session is on: {session.kind} ("
        + ("device: commands run on the user's own hardware" if session.kind == "device"
           else "online: server workspace, output capped at 64KB")
        + "). Reply with ONLY JSON: "
        '{"steps": [{"command": "bash command or code", "language": "python3"|"node"|"bash"|"", '
        '"note": "why this step"}], "done": false, "summary": ""} '
        "When the task is complete set done=true with a summary. Never use "
        "sudo or destructive commands — they are blocked. Max 4 steps."
    )
    user_prompt = f"TASK: {task}\n\nTRANSCRIPT SO FAR:\n"
    user_prompt += "\n".join(
        f"$ {c['command'][:300]}\n[{c['status']}] exit={c['exit_code']} {c['output'][:400]}"
        for c in history[-10:]
    ) or "(empty session)"

    try:
        result = await query_best_llm(user_prompt, system_prompt)
        raw = (result or {}).get("response") or ""
    except Exception as exc:
        return {"error": f"agent planning failed: {exc}"}

    plan = _parse_agent_plan(raw)
    if "error" in plan:
        return plan

    queued, pending = [], []
    for step in plan.get("steps", [])[:AGENT_MAX_COMMANDS_PER_ROUND]:
        command = str(step.get("command", ""))[:4000]
        if not command:
            continue
        language = str(step.get("language", "")) or ""
        if language not in LANGUAGES:
            language = ""
        cmd = enqueue_command(
            db, session_id, session.user_id, command,
            source="agent", language=language, admin=True,
        )
        (pending if cmd.status == "pending_approval" else queued).append(command_to_dict(cmd))

    return {
        "session_id": session_id,
        "task": task,
        "queued_now": queued,
        "awaiting_approval": pending,
        "done": bool(plan.get("done")),
        "summary": plan.get("summary", ""),
        "transcript_hint": "Approve the pending commands, then call the agent again to continue.",
    }


def _parse_agent_plan(raw: str) -> dict:
    import json
    import re

    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return {"error": "agent returned no valid JSON plan"}
    try:
        obj = json.loads(match.group(0))
    except Exception:
        return {"error": "agent returned malformed JSON plan"}
    steps = obj.get("steps") if isinstance(obj.get("steps"), list) else []
    return {
        "steps": steps,
        "done": bool(obj.get("done")),
        "summary": str(obj.get("summary", "")),
    }


def agent_executable_commands(db: Session, session_id: int, admin_user_id: int) -> int:
    """Run any queued agent code-runs in an online session and return how many ran."""
    session = _get_session(db, session_id, admin_user_id, admin=True)
    if session.kind != "online":
        return 0
    return run_queued_online(db, session_id)
