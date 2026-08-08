"""
EditOps tests — patches, symbol edits, renames, file ops, verification.
"""
import subprocess
from pathlib import Path

import pytest

from app.core.editops import (
    EditError,
    apply_patch,
    create_file,
    delete_file,
    move_file,
    rename_symbol,
    replace_symbol,
    search_references,
    verify_changed,
)
from app.core.workspace import Workspace


@pytest.fixture()
def ws(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
    )
    (repo / "app.ts").write_text("export function hello() {\n  return 1;\n}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    w = Workspace(repo, "edit-1").create()
    yield w
    w.destroy()


def _py(ws: Workspace) -> str:
    return (ws.path / "calc.py").read_text()


# ── apply_patch ──────────────────────────────────────────────

def test_apply_patch_valid(ws: Workspace):
    patch = (
        "diff --git a/calc.py b/calc.py\n"
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def add(a, b):\n"
        "-    return a + b\n"
        "+    return a + b + 1\n"
        " \n"
    )
    result = apply_patch(ws, patch)
    assert result["applied"] is True
    assert "return a + b + 1" in _py(ws)


def test_apply_patch_rejects_escape(ws: Workspace):
    patch = "--- a/../../etc/passwd\n+++ b/../../etc/passwd\n@@ -1 +1 @@\n-x\n+y\n"
    with pytest.raises(EditError):
        apply_patch(ws, patch)


def test_apply_patch_rejects_conflict(ws: Workspace):
    patch = (
        "diff --git a/calc.py b/calc.py\n"
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -99,1 +99,1 @@\n"
        "-nothing\n"
        "+else\n"
    )
    with pytest.raises(EditError):
        apply_patch(ws, patch)
# ── replace_symbol ───────────────────────────────────────────

def test_replace_python_function(ws: Workspace):
    replace_symbol(ws, "calc.py", "add", "def add(a, b):\n    return a * 2\n")
    content = _py(ws)
    assert "return a * 2" in content
    assert "return a + b" not in content
    assert "def sub(a, b):" in content  # untouched sibling


def test_replace_missing_symbol(ws: Workspace):
    with pytest.raises(EditError):
        replace_symbol(ws, "calc.py", "multiply", "def multiply(): pass\n")


def test_replace_ts_function(ws: Workspace):
    replace_symbol(ws, "app.ts", "hello", "export function hello() {\n  return 42;\n}")
    content = (ws.path / "app.ts").read_text()
    assert "return 42" in content
    assert "return 1" not in content


# ── rename_symbol ────────────────────────────────────────────

def test_rename_symbol(ws: Workspace):
    rename_symbol(ws, "calc.py", "add", "plus")
    content = _py(ws)
    assert "def plus(a, b):" in content
    assert "plus(a, b)" in content
    assert "def add" not in content


def test_rename_bad_identifier(ws: Workspace):
    with pytest.raises(EditError):
        rename_symbol(ws, "calc.py", "not-an-ident", "ok")


# ── references ───────────────────────────────────────────────

def test_search_references(ws: Workspace):
    refs = search_references(ws, "add")
    assert len(refs) == 1  # only the `def add` line — body uses a/b
    assert all("calc.py" in r["file"] for r in refs)
    assert refs[0]["line"] == 1


# ── file ops ─────────────────────────────────────────────────

def test_create_file(ws: Workspace):
    create_file(ws, "new.txt", "content\n")
    assert (ws.path / "new.txt").read_text() == "content\n"


def test_create_file_escape_rejected(ws: Workspace):
    with pytest.raises(EditError):
        create_file(ws, "../evil.txt", "x")


def test_delete_requires_approval(ws: Workspace):
    with pytest.raises(EditError):
        delete_file(ws, "calc.py")
    delete_file(ws, "calc.py", approved=True)
    assert not (ws.path / "calc.py").exists()


def test_move_file(ws: Workspace):
    create_file(ws, "src.txt", "hello")
    move_file(ws, "src.txt", "dst.txt")
    assert (ws.path / "dst.txt").read_text() == "hello"
    assert not (ws.path / "src.txt").exists()


# ── verify_changed ───────────────────────────────────────────

def test_verify_changed_exact(ws: Workspace):
    (ws.path / "calc.py").write_text("def add(a, b):\n    return a + b + 1\n")
    assert verify_changed(ws, ["calc.py"])["verified"] is True


def test_verify_changed_unexpected(ws: Workspace):
    (ws.path / "calc.py").write_text("x = 1\n")
    (ws.path / "oops.txt").write_text("unexpected\n")
    with pytest.raises(EditError):
        verify_changed(ws, ["calc.py"])
