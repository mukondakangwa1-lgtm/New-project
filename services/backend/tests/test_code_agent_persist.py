"""
Code agent persistence wiring tests — proposals mirror to SQLite through
create/approve/commit and survive a commit hash.
"""
import subprocess
from pathlib import Path

import pytest

from app.core.code_agent import (
    approve_proposal,
    commit_approved_changes,
    create_proposal,
    reject_proposal,
    set_repo_path,
)
from tests.conftest import TestSessionLocal


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
    subprocess.run(["git", "checkout", "-q", "-b", "kudos-task/persist"], cwd=root, check=True)
    return root


@pytest.fixture()
def _use_test_db(monkeypatch):
    import app.core.database as database_mod

    monkeypatch.setattr(database_mod, "SessionLocal", TestSessionLocal)


@pytest.fixture()
def proposal(repo: Path, _use_test_db):
    set_repo_path(str(repo))
    p = create_proposal(
        "Persist me",
        "Store this proposal",
        "improve",
        [{"file": "a.txt", "action": "modify", "content_preview": "new"}],
    )
    yield p


def test_create_mirrors_to_db(proposal):
    from app.models import SandboxProposal

    db = TestSessionLocal()
    try:
        row = db.query(SandboxProposal).filter(SandboxProposal.uuid == proposal.uuid).first()
        assert row is not None
        assert row.title == "Persist me"
        assert row.status == "pending"
        assert "a.txt" in (row.files_changed or "")
    finally:
        db.close()


def test_approve_syncs_status(proposal):
    from app.models import SandboxProposal

    approve_proposal(proposal.id)
    db = TestSessionLocal()
    try:
        row = db.query(SandboxProposal).filter(SandboxProposal.uuid == proposal.uuid).first()
        assert row.status == "approved"
    finally:
        db.close()


def test_reject_syncs_status(proposal):
    from app.models import SandboxProposal

    reject_proposal(proposal.id)
    db = TestSessionLocal()
    try:
        row = db.query(SandboxProposal).filter(SandboxProposal.uuid == proposal.uuid).first()
        assert row.status == "rejected"
    finally:
        db.close()


def test_commit_syncs_hash(repo: Path, proposal):
    from app.models import SandboxProposal

    approve_proposal(proposal.id)
    (repo / "a.txt").write_text("new content\n")
    result = commit_approved_changes(proposal.id, approval=True)
    assert result.get("commit_hash")
    db = TestSessionLocal()
    try:
        row = db.query(SandboxProposal).filter(SandboxProposal.uuid == proposal.uuid).first()
        assert row.status == "committed"
        assert row.commit_hash == result["commit_hash"]
    finally:
        db.close()


def test_get_git_status(repo: Path, _use_test_db):
    from app.core.code_agent import get_git_status, set_repo_path

    set_repo_path(str(repo))
    (repo / "b.txt").write_text("b\n")
    status = get_git_status()
    assert status["branch"] == "kudos-task/persist"
    assert status["protected"] is False
    assert "b.txt" in status["untracked"]
    assert status["recent_commits"], "recent commits should be populated"
    assert "diff_stat" in status
