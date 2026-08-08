"""
Tooling tests — command discovery, environment detection, dependency install.
"""
import json
import subprocess
from pathlib import Path

import pytest

from app.core.tooling import (
    ToolingError,
    detect_environment,
    discover_commands,
    ensure_venv,
    install_dependencies,
)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "services" / "backend").mkdir(parents=True)
    (root / "frontend").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "services" / "backend" / "requirements.txt").write_text("fastapi\n")
    (root / "frontend" / "package.json").write_text(
        json.dumps({"scripts": {"lint": "next lint", "build": "next build"},
                    "devDependencies": {"typescript": "^5"}})
    )
    return root


def test_discover_npm_scripts(repo: Path):
    cmds = discover_commands(repo)
    names = [c.name for c in cmds]
    assert "npm:lint" in names
    assert "npm:build" in names


def test_discover_backend_defaults(repo: Path):
    cmds = discover_commands(repo)
    kinds = {c.name: c.kind for c in cmds}
    assert kinds.get("pytest") == "test"
    assert kinds.get("ruff") == "lint"
    assert "compileall" in kinds


def test_discover_ci_commands(repo: Path):
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "name: CI\njobs:\n  b:\n    steps:\n      - run: pytest tests/ -q\n      - run: ruff check app/\n"
    )
    cmds = discover_commands(repo)
    ci = [c for c in cmds if c.framework == "ci"]
    assert len(ci) >= 1
    assert any("pytest" in " ".join(c.command) for c in ci)


def test_discover_makefile(repo: Path):
    (repo / "Makefile").write_text(
        "test: ## Run tests\n\tpytest tests/\nlint: ## Lint\n\truff check .\n"
    )
    cmds = discover_commands(repo)
    names = [c.name for c in cmds]
    assert "make:test" in names and "make:lint" in names


def test_detect_environment(repo: Path):
    env = detect_environment(repo)
    assert env.python
    assert env.python_version
    assert env.venv_exists is False
    assert env.npm_available is not False


def test_ensure_venv_creates(repo: Path):
    if not subprocess.run(["python3", "--version"], capture_output=True).returncode == 0:
        pytest.skip("python3 unavailable")
    py = ensure_venv(repo)
    assert Path(py).exists()
    assert "venv" in py


def test_install_dependencies_backend_only(repo: Path):
    if not subprocess.run(["python3", "--version"], capture_output=True).returncode == 0:
        pytest.skip("python3 unavailable")
    # Empty requirements = deterministic success without network access
    (repo / "services" / "backend" / "requirements.txt").write_text("")
    ensure_venv(repo)
    result = install_dependencies(repo, targets=["backend"], timeout=300)
    assert result["installed"] == ["backend"]
    assert result["errors"] == []


def test_install_reports_pip_failures(repo: Path):
    if not subprocess.run(["python3", "--version"], capture_output=True).returncode == 0:
        pytest.skip("python3 unavailable")
    ensure_venv(repo)
    (repo / "services" / "backend" / "requirements.txt").write_text("fastapi==99.99.99\n")
    result = install_dependencies(repo, targets=["backend"], timeout=120)
    assert result["errors"], "pip failure should be reported"


def test_install_unknown_target(repo: Path):
    result = install_dependencies(repo, targets=["bogus"])
    assert result["errors"]


def test_install_missing_requirements(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = install_dependencies(empty, targets=["backend"])
    assert result["errors"], "missing requirements should be reported"
