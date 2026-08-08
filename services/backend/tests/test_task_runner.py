"""
Persistence tests — SandboxProposal/SandboxLog/AgentTask models, migration
chain, and task_runner execution with sandbox bounds.
"""
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.core import task_runner
from app.core.task_runner import TaskRunnerError, create_task, get_task, list_logs, run_task
from app.core.workspace import Workspace
from tests.conftest import TestSessionLocal


@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch):
    """Route task_runner persistence to the session test database."""
    monkeypatch.setattr(task_runner, "SessionLocal", TestSessionLocal)


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
def ws(repo: Path) -> Workspace:
    w = Workspace(repo, "task-1").create()
    yield w
    w.destroy()


def _drop_tables():
    from app.core.database import Base
    from sqlalchemy import create_engine
    from tests.conftest import engine as test_engine

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def test_models_registered():
    from app.core.database import Base

    names = {c.name for c in Base.metadata.sorted_tables}
    assert "kudos_sandbox_proposals" in names
    assert "kudos_sandbox_logs" in names
    assert "kudos_agent_tasks" in names


def test_proposal_row(ws: Workspace):
    _drop_tables()
    db = TestSessionLocal()
    try:
        from app.models import SandboxProposal

        p = SandboxProposal(
            uuid="abc-123",
            title="Improve API",
            description="d",
            category="improve",
            status="pending",
            workspace=ws.path.name,
            files_changed='[{"file": "a.py"}]',
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        assert p.id is not None
        assert p.status == "pending"
        got = db.query(SandboxProposal).filter_by(uuid="abc-123").first()
        assert got is not None and got.title == "Improve API"
    finally:
        db.close()


def test_create_task_requires_workspace():
    _drop_tables()
    with pytest.raises(TaskRunnerError):
        create_task("run_command", {"command": "ls"})


def test_create_task_unknown_type(ws: Workspace):
    _drop_tables()
    with pytest.raises(TaskRunnerError):
        create_task("evil_thing", {"workspace": str(ws.path)})


def test_create_and_run_success(ws: Workspace):
    _drop_tables()
    task = create_task("run_command", {
        "workspace": str(ws.path),
        "command": "python3 -c 'print(42)'",
        "timeout": 30,
    })
    assert task.status == "pending"
    result = run_task(task.id)
    assert result["status"] == "done"
    assert result["exit_code"] == 0
    assert "42" in result["output"]

    got = get_task(task.id)
    assert got["status"] == "done"
    assert got["result"]["exit_code"] == 0

    logs = list_logs(workspace=ws.path.name)
    assert any(l["status"] == "done" and "42" in l["output"] for l in logs)


def test_run_failing_command(ws: Workspace):
    _drop_tables()
    task = create_task("run_command", {
        "workspace": str(ws.path),
        "command": "python3 -c 'exit(3)'",
        "timeout": 30,
    })
    result = run_task(task.id)
    assert result["status"] == "failed"
    assert result["exit_code"] == 3
    logs = list_logs(workspace=ws.path.name)
    assert logs and logs[0]["exit_code"] == 3


def test_shell_chaining_refused(ws: Workspace):
    _drop_tables()
    task = create_task("run_command", {
        "workspace": str(ws.path),
        "command": "echo hi; rm -rf /",
        "timeout": 30,
    })
    result = run_task(task.id)
    assert result["status"] == "failed"
    assert "chaining" in result["error"]


def test_path_escape_refused(ws: Workspace):
    _drop_tables()
    task = create_task("run_command", {
        "workspace": str(ws.path),
        "command": "cat ../../etc/passwd",
        "timeout": 30,
    })
    result = run_task(task.id)
    assert result["status"] == "failed"


def test_run_task_missing():
    _drop_tables()
    result = run_task(999999)
    assert result["status"] == "failed"
    assert "not found" in result["error"]


def test_get_task_missing():
    _drop_tables()
    assert get_task(999999) is None


def test_workspace_path_must_be_inside_workspaces_dir(repo: Path):
    _drop_tables()
    with pytest.raises(TaskRunnerError):
        create_task("run_command", {"workspace": str(repo), "command": "ls"})
