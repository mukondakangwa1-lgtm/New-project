"""
GitOps tests — protected branches, allowlist staging, conflict detection,
commit/push/PR approval gates.
"""
import subprocess
from pathlib import Path

import pytest

from app.core.gitops import (
    GitOpsError,
    PROTECTED_BRANCHES,
    assert_task_branch,
    commit,
    create_task_branch,
    detect_conflicts,
    diff_sections,
    push,
    repo_state,
    stage_files,
)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "a.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    return root


def test_protected_branches_constant():
    assert "main" in PROTECTED_BRANCHES
    assert "master" in PROTECTED_BRANCHES
    assert "develop" in PROTECTED_BRANCHES


def test_assert_task_branch_refuses_protected(repo: Path):
    with pytest.raises(GitOpsError):
        assert_task_branch(repo)
    # with approval it proceeds
    state = assert_task_branch(repo, approval=True)
    assert state.protected is True


def test_assert_task_branch_allows_feature_branch(repo: Path):
    create_task_branch(repo, "my-task")
    state = assert_task_branch(repo)
    assert state.branch == "kudos-task/my-task"
    assert state.protected is False


def test_create_task_branch_refuses_dirty(repo: Path):
    (repo / "a.txt").write_text("changed\n")
    with pytest.raises(GitOpsError):
        create_task_branch(repo, "x")


def test_stage_allowlist_only(repo: Path):
    (repo / "b.txt").write_text("b\n")
    (repo / "c.txt").write_text("c\n")
    result = stage_files(repo, ["b.txt"], repo_root=repo)
    assert result["staged"] == ["b.txt"]
    state = repo_state(repo)
    assert "b.txt" in state.staged
    assert "c.txt" in state.untracked  # never staged


def test_stage_rejects_protected_paths(repo: Path):
    (repo / ".env").write_text("SECRET=1\n")
    with pytest.raises(GitOpsError):
        stage_files(repo, [".env"], repo_root=repo)


def test_stage_rejects_escape(repo: Path):
    with pytest.raises(GitOpsError):
        stage_files(repo, ["../outside"], repo_root=repo)


def test_repo_state_sections(repo: Path):
    create_task_branch(repo, "st")
    (repo / "a.txt").write_text("modified\n")  # unstaged
    (repo / "b.txt").write_text("new\n")  # untracked
    stage_files(repo, ["a.txt"], repo_root=repo)  # now staged
    state = repo_state(repo)
    assert "a.txt" in state.staged
    assert "b.txt" in state.untracked
    sections = diff_sections(repo)
    assert "modified" in sections["staged"]
    assert "b.txt" not in sections["staged"]


def test_unrelated_changes_detected(repo: Path):
    (repo / "a.txt").write_text("x\n")
    (repo / "other.txt").write_text("y\n")
    state = repo_state(repo)
    unrelated = state.unrelated_changes(["a.txt"])
    assert "other.txt" in unrelated
    assert "a.txt" not in unrelated


def test_commit_allowlist(repo: Path):
    create_task_branch(repo, "c1")
    (repo / "a.txt").write_text("new content\n")
    result = commit(repo, "feat: change a", ["a.txt"], repo_root=repo)
    assert result["branch"] == "kudos-task/c1"
    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=repo, capture_output=True, text=True).stdout
    assert "feat: change a" in log


def test_commit_nothing_to_commit(repo: Path):
    create_task_branch(repo, "c2")
    with pytest.raises(GitOpsError):
        commit(repo, "nope", ["a.txt"], repo_root=repo)


def test_push_requires_approval(repo: Path):
    create_task_branch(repo, "p1")
    with pytest.raises(GitOpsError):
        push(repo)


def test_push_no_remote_errors(repo: Path):
    # without any remote, push fails even when approved
    with pytest.raises(GitOpsError):
        push(repo, approved=True)


def test_detect_conflicts_no_remote(repo: Path):
    result = detect_conflicts(repo)
    assert result["checked"] is False
    assert result["reason"]


def test_fetch_remote_absent(repo: Path):
    from app.core.gitops import fetch_remote

    result = fetch_remote(repo)
    assert result["fetched"] is False
    assert result["remote"] is None
