"""
Task runner API tests — create/run tasks, list, detail, logs; admin-only.
"""
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.workspace import Workspace
from app.main import app
from tests.conftest import TestSessionLocal, login, promote_to_admin, register_user

client = TestClient(app)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "x.txt").write_text("x\n")
    subprocess.run(["git", "add", "x.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    return root


@pytest.fixture()
def admin_headers():
    import uuid

    email = f"task_admin_{uuid.uuid4().hex[:8]}@example.com"
    register_user(client, email)
    promote_to_admin(email)
    return login(client, email)


@pytest.fixture()
def ws(repo: Path) -> Workspace:
    w = Workspace(repo, "api-task").create()
    yield w
    w.destroy()


def test_run_task_success(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "python3 -c 'print(7)'",
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "done"
    assert data["exit_code"] == 0
    assert "7" in data["output"]


def test_run_task_chaining_refused(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "echo hi; rm -rf /",
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "failed"
    assert "chaining" in data["error"].lower()


@pytest.mark.parametrize("bad_command,reason", [
    ("cat /etc/passwd", "escapes"),
    ("echo $(id)", "chaining"),
    ("cat /etc/hostname && echo pwned", "chaining"),
])
def test_run_task_sandbox_refusals(ws, admin_headers, monkeypatch, bad_command, reason):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": bad_command,
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "failed"
    assert reason in data["error"].lower()


def test_run_task_allows_workspace_local_absolute_path(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": f"cat {ws.path}/x.txt",
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "done", data
    assert "x" in data["output"]


@pytest.mark.parametrize("bad_command,reason", [
    # absolute host paths nested inside interpreter payloads must be caught
    ("sh -c 'cat /etc/passwd'", "escapes"),
    ("bash -c 'rm -rf /tmp/evil'", "escapes"),
    ("python3 -c 'import os; os.remove(\"/etc/hosts\")'", "escapes"),
    ("env sh -c 'cat /etc/passwd'", "escapes"),
    # shell -c strings can smuggle host paths via env expansion we cannot
    # audit statically ($HOME, ~), so shell code execution is refused outright
    ("sh -c 'cat $HOME/.ssh/id_rsa'", "shell -c"),
    ("bash -c 'echo $HOME'", "shell -c"),
])
def test_run_task_interpreter_escapes_refused(ws, admin_headers, monkeypatch, bad_command, reason):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": bad_command,
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "failed", data
    assert reason in data["error"].lower(), data["error"]


def test_run_task_allows_git_c_flag_and_script_files(ws: Workspace, admin_headers, monkeypatch):
    """git -c <key>=<value> and in-workspace shell scripts are legitimate —
    only code executed via a shell -c flag is refused."""
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "git -c user.name=t log --oneline -1",
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "done", r.json()

    (ws.path / "s.sh").write_text("echo ok\n")
    r2 = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "sh -e s.sh",
        "timeout": 30,
    })
    assert r2.status_code == 201, r2.text
    data = r2.json()
    assert data["status"] == "done", data
    assert "ok" in data["output"]


def test_run_task_whitespace_command_refused(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "   ",
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "failed", data
    assert "empty" in data["error"].lower()
    d = client.get(f"/api/v1/kudos/agent/tasks/{data['task_id']}", headers=admin_headers)
    assert d.json()["status"] == "failed", "row must not stay running"


def test_sandbox_env_scrubbed(ws: Workspace, admin_headers, monkeypatch):
    """Task subprocesses must not see backend secrets or the host HOME."""
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    monkeypatch.setenv("SECRET_KEY", "sup3r-secret")
    monkeypatch.setenv("MY_AUTH_TOKEN", "tok-123")
    monkeypatch.setenv("DATABASE_URL", "postgres://secret")
    monkeypatch.setenv("FOO_BAR", "hello")

    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "env",
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "done", data
    for secret in ("SECRET_KEY", "MY_AUTH_TOKEN", "DATABASE_URL", "sup3r-secret", "tok-123"):
        assert secret not in data["output"], f"{secret} leaked into sandbox env"
    assert "FOO_BAR=hello" in data["output"], "benign vars must still pass through"


def test_sandbox_home_confined(ws: Workspace, admin_headers, monkeypatch):
    """HOME is redirected to the workspace, so ~ cannot reach host files."""
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "python3 -c 'import os; print(os.environ.get(\"HOME\"))'",
        "timeout": 30,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "done", data
    assert str(ws.path) in data["output"]


def test_edit_apply_happy_path(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "edit_apply",
        "workspace": str(ws.path),
        "edits": [
            {"path": "new_file.txt", "action": "create", "content": "hello\n"},
            {"path": "x.txt", "action": "append", "content": "appended"},
            {"path": "x.txt", "action": "insert", "line": 1, "content": "mid"},
        ],
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "done", data
    assert data["applied"] == 3
    assert data["refused"] == 0
    assert (ws.path / "new_file.txt").read_text() == "hello\n"
    assert (ws.path / "x.txt").read_text().startswith("x\nmid")


def test_edit_apply_refusals(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "edit_apply",
        "workspace": str(ws.path),
        "edits": [
            {"path": "../escape.txt", "action": "create", "content": "x"},
            {"path": ".env", "action": "create", "content": "SECRET=1"},
            {"path": "/etc/hosts", "action": "append", "content": "x"},
            {"path": "fine.txt", "action": "create", "content": "ok"},
        ],
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "failed", data
    assert data["applied"] == 1
    assert data["refused"] == 3
    assert "escape" in data["error"]
    assert not (ws.repo_root / "escape.txt").exists()
    assert not (ws.path / ".env").exists()


def test_edit_apply_requires_edits(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "edit_apply",
        "workspace": str(ws.path),
        "edits": [],
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "failed"
    assert "edits" in data["error"].lower()


def test_run_task_missing_workspace(admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "command": "ls",
    })
    assert r.status_code == 400, r.text


def test_run_task_foreign_workspace(admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": "/etc",
        "command": "ls",
    })
    assert r.status_code == 400, r.text
    assert "workspace" in r.json()["detail"].lower()


def test_list_and_detail(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "python3 -c 'print(1)'",
        "timeout": 30,
    })
    r = client.get("/api/v1/kudos/agent/tasks", headers=admin_headers)
    assert r.status_code == 200
    tasks = r.json()["tasks"]
    assert tasks, "task should be listed"
    tid = tasks[0]["id"]
    r2 = client.get(f"/api/v1/kudos/agent/tasks/{tid}", headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "done"


def test_task_logs(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "python3 -c 'print(2)'",
        "timeout": 30,
    })
    r = client.get("/api/v1/kudos/agent/tasks/logs", headers=admin_headers)
    assert r.status_code == 200
    logs = r.json()["logs"]
    assert any("python3" in l["command"] for l in logs)


def test_requires_admin(ws: Workspace):
    # Clear the persisted HttpOnly session cookie so these requests are
    # genuinely unauthenticated.
    client.cookies.clear()
    r = client.post("/api/v1/kudos/agent/tasks", json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "ls",
    })
    assert r.status_code in (401, 403)
    r2 = client.get("/api/v1/kudos/agent/tasks")
    assert r2.status_code in (401, 403)


def test_unknown_task_type(ws: Workspace, admin_headers, monkeypatch):
    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "evil",
        "workspace": str(ws.path),
        "command": "ls",
    })
    assert r.status_code == 400
    assert "task type" in r.json()["detail"].lower()


def test_task_async_mode(ws: Workspace, admin_headers, monkeypatch):
    """wait=false queues the task and returns immediately; polling sees it
    progress through running to done with the full result."""
    import time

    from app.core import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)
    r = client.post("/api/v1/kudos/agent/tasks", headers=admin_headers, json={
        "task_type": "run_command",
        "workspace": str(ws.path),
        "command": "python3 -c 'print(42)'",
        "timeout": 30,
        "wait": False,
    })
    assert r.status_code == 201, r.text
    queued = r.json()
    assert queued["status"] == "pending"
    tid = queued["task_id"]

    deadline = time.time() + 15
    final = None
    while time.time() < deadline:
        d = client.get(f"/api/v1/kudos/agent/tasks/{tid}", headers=admin_headers)
        assert d.status_code == 200
        body = d.json()
        assert body["status"] in ("pending", "running", "done", "failed")
        if body["status"] in ("done", "failed"):
            final = body
            break
        time.sleep(0.2)
    assert final, "task did not finish in time"
    assert final["status"] == "done", final
    assert "42" in final["result"]["output"]
