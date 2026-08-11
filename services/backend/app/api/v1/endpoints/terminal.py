"""KUDOS Terminal API — open terminals on any device, or online.

Sessions:
  POST /sessions            open a terminal (device_id given → device; none → online)
  GET  /sessions            list my sessions
  GET  /sessions/{id}       full transcript
  POST /sessions/{id}/command   issue a command (source user → runs; agent → approval)
  POST /sessions/{id}/code      write + run a code file (syntax-bounded)
  POST /sessions/{id}/close     close the terminal
  POST /sessions/{id}/agent     one agent round (superadmin)

Approvals (superadmin):
  GET  /approvals           commands awaiting approval
  POST /commands/{id}/approve

Device channel (X-Device-Token):
  GET  /commands            claim the next queued commands
  POST /commands/{id}/result
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.terminal import (
    approve_command,
    claim_next_for_device,
    close_session,
    create_session,
    enqueue_command,
    execute_online,
    list_sessions,
    pending_approvals,
    run_agent_round,
    session_to_dict,
    submit_result,
    transcript,
)
from app.models import User

router = APIRouter()


class SessionCreate(BaseModel):
    device_id: int | None = None
    name: str = Field(default="kudos-terminal", max_length=120)


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="user", pattern="^(user|agent)$")
    language: str = Field(default="", max_length=20)


class CodeRunRequest(BaseModel):
    language: str = Field(pattern="^(python3|node|bash)$")
    code: str = Field(min_length=1, max_length=20000)


class ApproveRequest(BaseModel):
    command_id: int


class ResultRequest(BaseModel):
    exit_code: int
    output: str = ""


class AgentRequest(BaseModel):
    task: str = Field(min_length=3, max_length=2000)


# ──────────────────────────────────────────────
# USER / ADMIN SESSION ENDPOINTS
# ──────────────────────────────────────────────


@router.post("/sessions", status_code=201)
def open_session_endpoint(
    body: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open a terminal on a device, or online (superadmin)."""
    try:
        session = create_session(
            db,
            current_user.id,
            device_id=body.device_id,
            name=body.name,
            admin=current_user.is_admin,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session_to_dict(session)


@router.get("/sessions")
def list_sessions_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"sessions": list_sessions(db, current_user.id)}


@router.get("/sessions/{session_id}")
def session_transcript_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return transcript(db, session_id, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/command")
def issue_command_endpoint(
    session_id: int,
    body: CommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a command. source=user runs when possible; source=agent waits
    for superadmin approval (unless it is a code run with a language)."""
    try:
        cmd = enqueue_command(
            db,
            session_id,
            current_user.id,
            body.command,
            source=body.source,
            language=body.language,
            admin=current_user.is_admin,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if cmd.status == "queued":
        session = _session_row(db, cmd.session_id)
        if session and session.kind == "online":
            return execute_online(db, cmd)
    return _command_payload(cmd)


@router.post("/sessions/{session_id}/code")
def run_code_endpoint(
    session_id: int,
    body: CodeRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Write the code into the session workspace and run it."""
    try:
        cmd = enqueue_command(
            db,
            session_id,
            current_user.id,
            body.code,
            source="user",
            language=body.language,
            admin=current_user.is_admin,
        )
        session = _session_row(db, cmd.session_id)
        if session and session.kind == "online":
            return execute_online(db, cmd)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _command_payload(cmd)


@router.post("/sessions/{session_id}/close")
def close_session_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return close_session(db, session_id, current_user.id, admin=current_user.is_admin)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/agent")
async def agent_round_endpoint(
    session_id: int,
    body: AgentRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """One agent round: KUDOS plans the next commands for the task.

    Shell commands enter pending_approval; code runs execute immediately on
    online sessions. Approve pending commands, then call again to continue.
    """
    try:
        return await run_agent_round(db, session_id, body.task, admin.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ──────────────────────────────────────────────
# APPROVALS (superadmin)
# ──────────────────────────────────────────────


@router.get("/approvals")
def approvals_endpoint(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return {"awaiting_approval": pending_approvals(db, admin.id)}


@router.post("/commands/{command_id}/approve")
def approve_command_endpoint(
    command_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        cmd = approve_command(db, command_id, admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Online sessions execute approved commands right away; device sessions
    # wait for the device agent to claim them on its next poll.
    from app.models import KudosTerminalCommand

    session = _session_row(db, cmd["session_id"])
    if session and session.kind == "online":
        return execute_online(db, db.get(KudosTerminalCommand, command_id))
    return cmd


# ──────────────────────────────────────────────
# DEVICE CHANNEL
# ──────────────────────────────────────────────


@router.get("/commands")
def device_claim_endpoint(
    device_token: str = Header(..., alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """Claim the next queued commands for this device (device agent polls)."""
    try:
        return {"commands": claim_next_for_device(db, device_token)}
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/commands/{command_id}/result")
def device_result_endpoint(
    command_id: int,
    body: ResultRequest,
    device_token: str = Header(..., alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    try:
        return submit_result(db, device_token, command_id, body.exit_code, body.output)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────


def _session_row(db: Session, session_id: int):
    from app.models import KudosTerminalSession

    return db.get(KudosTerminalSession, session_id)


def _command_payload(cmd) -> dict:
    from app.core.terminal import command_to_dict

    return command_to_dict(cmd)
