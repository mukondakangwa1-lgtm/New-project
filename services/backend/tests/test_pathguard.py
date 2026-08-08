"""
PathGuard tests — path validation, traversal, symlink escape, protected files.
"""
import os
from pathlib import Path

import pytest

from app.core.pathguard import (
    PROTECTED_NAMES,
    PathError,
    is_inside,
    resolve_inside,
    validate_absolute,
)


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    root.mkdir()
    return root


def test_resolve_normal_file(ws: Path):
    p = resolve_inside(ws, "app/main.py", allow_missing=True)
    assert p == (ws / "app" / "main.py").resolve()


def test_rejects_traversal(ws: Path):
    with pytest.raises(PathError):
        resolve_inside(ws, "../outside.txt")


def test_rejects_absolute_escape(ws: Path):
    with pytest.raises(PathError):
        resolve_inside(ws, "/etc/passwd")


def test_rejects_symlink_escape(ws: Path):
    outside = ws.parent / "secret.txt"
    outside.write_text("top secret")
    (ws / "link").symlink_to(outside)
    with pytest.raises(PathError):
        resolve_inside(ws, "link/secret.txt")
    with pytest.raises(PathError):
        resolve_inside(ws, "link")


def test_rejects_protected_names(ws: Path):
    for name in (".env", ".env.prod", "id_rsa", "credentials.json", "server.key", ".git/config"):
        with pytest.raises(PathError):
            resolve_inside(ws, name)


def test_rejects_protected_nested(ws: Path):
    (ws / ".env").mkdir(exist_ok=True)
    with pytest.raises(PathError):
        resolve_inside(ws, ".env/secret.txt")


def test_is_inside(ws: Path):
    assert is_inside(ws, ws / "a" / "b")
    assert not is_inside(ws, ws.parent / "b")


def test_validate_absolute_system_paths():
    with pytest.raises(PathError):
        validate_absolute("/etc/passwd")
    with pytest.raises(PathError):
        validate_absolute(os.path.expanduser("~/.ssh/id_rsa"))
    with pytest.raises(PathError):
        validate_absolute("/root/.ssh/authorized_keys")


def test_protected_names_defined():
    assert ".env" in PROTECTED_NAMES
    assert "id_rsa" in PROTECTED_NAMES
