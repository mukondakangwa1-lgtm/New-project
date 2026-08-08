"""
Workspace tests — git worktree isolation, snapshot, rollback, patch, cleanup.
"""
import subprocess
from pathlib import Path

import pytest

from app.core.workspace import Workspace, cleanup_all


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A real git repository to act as the project root."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "hello.txt").write_text("hello\n")
    subprocess.run(["git", "add", "hello.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
    (root / ".gitignore").write_text(".kudos_workspaces/\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "gitignore"], cwd=root, check=True)
    return root


def test_create_detached_worktree(repo: Path):
    ws = Workspace(repo, "task-1").create()
    assert ws.path.exists()
    assert (ws.path / "hello.txt").read_text() == "hello\n"
    # Main tree must stay clean
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert status.strip() == ""
    ws.destroy()
    assert not ws.path.exists()


def test_edits_do_not_leak_to_main_tree(repo: Path):
    ws = Workspace(repo, "task-2").create()
    (ws.path / "hello.txt").write_text("modified\n")
    patch = ws.patch()
    assert "hello.txt" in patch
    # Main tree untouched
    content = (repo / "hello.txt").read_text()
    assert content == "hello\n"
    ws.destroy()


def test_rollback_restores_snapshot(repo: Path):
    ws = Workspace(repo, "task-3").create()
    (ws.path / "hello.txt").write_text("changed\n")
    (ws.path / "new.txt").write_text("untracked\n")
    ws.rollback()
    assert (ws.path / "hello.txt").read_text() == "hello\n"
    assert not (ws.path / "new.txt").exists()
    assert ws.patch().strip() == ""
    ws.destroy()


def test_files_changed_and_patch(repo: Path):
    ws = Workspace(repo, "task-4").create()
    (ws.path / "a.txt").write_text("A\n")
    (ws.path / "hello.txt").write_text("hello world\n")
    assert set(ws.files_changed()) == {"a.txt", "hello.txt"}
    assert "a.txt" in ws.patch()
    assert "hello world" in ws.patch()
    ws.destroy()


def test_create_branch_worktree(repo: Path):
    ws = Workspace(repo, "task-5").create(create_branch=True)
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=ws.path, capture_output=True, text=True
    ).stdout.strip()
    assert branch == "kudos-task/task-5"
    ws.destroy()


def test_duplicate_workspace_name(repo: Path):
    ws = Workspace(repo, "task-6").create()
    with pytest.raises(Exception):
        Workspace(repo, "task-6").create()
    ws.destroy()


def test_cleanup_all(repo: Path):
    w1 = Workspace(repo, "clean-1").create()
    w2 = Workspace(repo, "clean-2").create()
    assert cleanup_all(repo) == 2
    assert not w1.path.exists()
    assert not w2.path.exists()
