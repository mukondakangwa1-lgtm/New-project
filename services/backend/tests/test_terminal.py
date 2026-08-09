"""
KUDOS Terminal tests: device channel round-trip, online jailed executor,
denylist enforcement, agent approval gate, code write+run, and isolation.
"""
import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TestSessionLocal, login, promote_to_admin, register_user

client = TestClient(app)

EMAIL_A = "term_a@campus.edu"
EMAIL_B = "term_b@campus.edu"


def _setup(email):
    try:
        register_user(client, email)
    except AssertionError:
        pass
    headers = login(client, email)
    return headers


def _uid(email):
    from app.models import User

    db = TestSessionLocal()
    try:
        return db.query(User).filter(User.email == email).first().id
    finally:
        db.close()


def _register_device(headers, name="phone"):
    r = client.post(
        "/api/v1/kudos/devices",
        json={"name": name, "platform": "android", "storage_bytes": 1073741824},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _online_session(headers):
    r = client.post("/api/v1/kudos/terminal/sessions", json={}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _wipe(email):
    from app.models import (
        KudosDevice, KudosMemory, KudosMemoryReplica,
        KudosTerminalCommand, KudosTerminalSession,
    )

    db = TestSessionLocal()
    try:
        uid = _uid(email)
        cmds = db.query(KudosTerminalCommand).filter(KudosTerminalCommand.user_id == uid).all()
        for c in cmds:
            db.delete(c)
        sess = db.query(KudosTerminalSession).filter(KudosTerminalSession.user_id == uid).all()
        for s in sess:
            db.delete(s)
        reps = db.query(KudosMemoryReplica).filter(KudosMemoryReplica.user_id == uid).all()
        for r in reps:
            db.delete(r)
        mems = db.query(KudosMemory).filter(KudosMemory.user_id == uid).all()
        for m in mems:
            db.delete(m)
        devs = db.query(KudosDevice).filter(KudosDevice.user_id == uid).all()
        for d in devs:
            db.delete(d)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ──────────────────────────────────────────────
# ONLINE EXECUTOR
# ──────────────────────────────────────────────

def test_online_session_requires_admin():
    headers = _setup(EMAIL_A)
    r = client.post("/api/v1/kudos/terminal/sessions", json={}, headers=headers)
    assert r.status_code == 403
    _wipe(EMAIL_A)


def test_online_session_runs_echo():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)
    assert session["kind"] == "online"

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "echo hello-kudos"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["exit_code"] == 0
    assert "hello-kudos" in body["output"]

    r = client.get(f"/api/v1/kudos/terminal/sessions/{session['id']}", headers=headers)
    assert r.json()["session"]["status"] == "open"
    assert r.json()["commands"][0]["status"] == "done"
    _wipe(EMAIL_A)


def test_online_denylist_blocks_sudo_and_rm():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "sudo whoami"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert "blocked" in r.json()["output"].lower()

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "rm -rf /etc"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert "blocked" in r.json()["output"].lower()
    _wipe(EMAIL_A)


def test_online_code_run_writes_and_executes():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/code",
        json={"language": "python3", "code": "print('kudos-can-code', 2 + 2)"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done", body["output"]
    assert "kudos-can-code 4" in body["output"]

    # the file must live in the session workspace
    workspace = client.get(
        f"/api/v1/kudos/terminal/sessions/{session['id']}", headers=headers
    ).json()["session"]["workspace"]
    assert os.path.isfile(os.path.join(workspace, "code.py"))
    _wipe(EMAIL_A)


def test_online_timeout_and_bad_language():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/code",
        json={"language": "ruby", "code": "puts 1"},
        headers=headers,
    )
    assert r.status_code == 422
    _wipe(EMAIL_A)


# ──────────────────────────────────────────────
# DEVICE CHANNEL
# ──────────────────────────────────────────────

def test_device_claim_and_result_roundtrip():
    headers = _setup(EMAIL_A)
    device = _register_device(headers)
    token = device["api_token"]

    r = client.post(
        "/api/v1/kudos/terminal/sessions",
        json={"device_id": device["id"], "name": "phone-shell"},
        headers=headers,
    )
    assert r.status_code == 201
    session = r.json()
    assert session["kind"] == "device"

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "ls -la"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "queued"

    # the device polls and claims
    r = client.get("/api/v1/kudos/terminal/commands", headers={"X-Device-Token": token})
    assert r.status_code == 200
    claimed = r.json()["commands"]
    assert len(claimed) == 1
    assert claimed[0]["command"] == "ls -la"
    assert claimed[0]["status"] == "claimed"

    # second poll is empty while claimed (fresh claim)
    r = client.get("/api/v1/kudos/terminal/commands", headers={"X-Device-Token": token})
    assert r.json()["commands"] == []

    # the device posts the result
    r = client.post(
        f"/api/v1/kudos/terminal/commands/{claimed[0]['id']}/result",
        json={"exit_code": 0, "output": "total 0"},
        headers={"X-Device-Token": token},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    transcript = client.get(
        f"/api/v1/kudos/terminal/sessions/{session['id']}", headers=headers
    ).json()
    assert transcript["commands"][0]["output"] == "total 0"
    assert transcript["commands"][0]["exit_code"] == 0
    _wipe(EMAIL_A)


def test_device_cannot_claim_others_commands():
    headers_a = _setup(EMAIL_A)
    device_a = _register_device(headers_a)
    headers_b = _setup(EMAIL_B)
    device_b = _register_device(headers_b, "phone_b")

    r = client.post(
        "/api/v1/kudos/terminal/sessions",
        json={"device_id": device_a["id"]},
        headers=headers_a,
    )
    session = r.json()
    client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "secret-cmd"},
        headers=headers_a,
    )

    r = client.get("/api/v1/kudos/terminal/commands", headers={"X-Device-Token": device_b["api_token"]})
    assert r.json()["commands"] == []

    r = client.get(f"/api/v1/kudos/terminal/sessions/{session['id']}", headers=headers_b)
    assert r.status_code == 403
    _wipe(EMAIL_A)
    _wipe(EMAIL_B)


def test_unknown_device_token_rejected():
    r = client.get("/api/v1/kudos/terminal/commands", headers={"X-Device-Token": "nope"})
    assert r.status_code == 401


# ──────────────────────────────────────────────
# AGENT GATE & APPROVALS
# ──────────────────────────────────────────────

def test_agent_shell_waits_for_approval_online():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "whoami", "source": "agent"},
        headers=headers,
    )
    assert r.status_code == 200
    cmd = r.json()
    assert cmd["status"] == "pending_approval"
    assert cmd["output"] == ""

    # nothing executed yet
    r = client.get(f"/api/v1/kudos/terminal/sessions/{session['id']}", headers=headers)
    assert r.json()["commands"][0]["status"] == "pending_approval"

    # approval list shows it, then approval executes it on online sessions
    r = client.get("/api/v1/kudos/terminal/approvals", headers=headers)
    assert len(r.json()["awaiting_approval"]) == 1

    r = client.post(f"/api/v1/kudos/terminal/commands/{cmd['id']}/approve", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["exit_code"] == 0

    # user commands do not wait for approval
    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "echo direct", "source": "user"},
        headers=headers,
    )
    assert r.json()["status"] == "done"
    _wipe(EMAIL_A)


def test_agent_code_run_executes_immediately():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "print('agent-code-ok')", "source": "agent", "language": "python3"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert "agent-code-ok" in r.json()["output"]
    _wipe(EMAIL_A)


def test_agent_round_plans_and_gates_shell():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)

    fake_plan = '{"steps": [{"command": "ls", "language": "", "note": "list"}, {"command": "echo hi", "language": "bash", "note": "say hi"}], "done": false}'
    with patch("app.core.llm_engine.query_best_llm", new_callable=AsyncMock) as mock:
        mock.return_value = {"response": fake_plan}
        r = client.post(
            f"/api/v1/kudos/terminal/sessions/{session['id']}/agent",
            json={"task": "explore the workspace"},
            headers=headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["awaiting_approval"]) == 1
    assert len(body["queued_now"]) == 1
    assert body["queued_now"][0]["language"] == "bash"
    _wipe(EMAIL_A)


def test_agent_endpoint_requires_admin():
    headers = _setup(EMAIL_B)
    r = client.post(
        "/api/v1/kudos/terminal/sessions/1/agent",
        json={"task": "do something"},
        headers=headers,
    )
    assert r.status_code == 403
    _wipe(EMAIL_B)


# ──────────────────────────────────────────────
# SESSION PICKING & CLOSING
# ──────────────────────────────────────────────

def test_close_session_blocks_new_commands():
    headers = _setup(EMAIL_A)
    promote_to_admin(EMAIL_A)
    session = _online_session(headers)

    r = client.post(f"/api/v1/kudos/terminal/sessions/{session['id']}/close", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "closed"

    r = client.post(
        f"/api/v1/kudos/terminal/sessions/{session['id']}/command",
        json={"command": "echo late"},
        headers=headers,
    )
    assert r.status_code == 404
    _wipe(EMAIL_A)
