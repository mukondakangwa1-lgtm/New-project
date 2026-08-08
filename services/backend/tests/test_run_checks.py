"""
RunChecks tests — gate running and failure classification.
"""
import subprocess
from pathlib import Path

import pytest

from app.core.run_checks import classify, run_gate, run_quality_gates, summarize
from app.core.tooling import QualityCommand


def _gate(name: str, kind: str) -> QualityCommand:
    return QualityCommand(name=name, command=["true"], cwd=".", kind=kind)


# ── classify ──────────────────────────────────────────────

def test_classify_success():
    assert classify("x", "test", 0, "1 passed", "", False) == "success"


def test_classify_test_failure():
    assert classify("pytest", "test", 1, "2 failed, 3 passed", "", False) == "test_failure"


def test_classify_type_error():
    out = "src/app.ts(5,3): error TS2322: Type 'number' not assignable"
    assert classify("tsc", "typecheck", 2, out, "", False) == "type_error"
    # kind fallback
    assert classify("tsc", "typecheck", 1, "", "", False) == "type_error"


def test_classify_lint_error():
    assert classify("ruff", "lint", 1, "F821 undefined name", "", False) == "code_error"


def test_classify_missing_env():
    out = "app.core.config: environment variable 'SECRET_KEY' not set"
    assert classify("pytest", "test", 1, out, "", False) == "missing_env"


def test_classify_database_error():
    out = "sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table"
    assert classify("pytest", "test", 1, out, "", False) == "database_error"


def test_classify_dependency_error():
    out = "ModuleNotFoundError: No module named 'fastapi'"
    assert classify("pytest", "test", 1, out, "", False) == "dependency_error"


def test_classify_network_error():
    out = "urllib3.exceptions.MaxRetryError: Failed to establish a new connection"
    assert classify("pip", "build", 1, out, "", False) == "network_error"


def test_classify_unresolvable_dependency():
    out = "ERROR: Could not find a version that satisfies the requirement fastapi==99.99.99"
    assert classify("pip", "build", 1, out, "", False) == "dependency_error"


def test_classify_timeout():
    assert classify("pytest", "test", 124, "", "", True) == "timeout"


def test_classify_infra():
    out = "docker: Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
    assert classify("compose", "build", 1, out, "", False) == "infrastructure"


# ── run_gate ──────────────────────────────────────────────

def test_run_gate_success(tmp_path: Path):
    gate = QualityCommand("echo", ["echo", "ok"], ".", "test")
    result = run_gate(tmp_path, gate)
    assert result.passed
    assert result.exit_code == 0


def test_run_gate_failure(tmp_path: Path):
    gate = QualityCommand("failing", ["python3", "-c", "raise SystemExit(3)"], ".", "test")
    result = run_gate(tmp_path, gate)
    assert not result.passed
    assert result.exit_code == 3


def test_run_gate_timeout(tmp_path: Path):
    gate = QualityCommand("slow", ["python3", "-c", "import time; time.sleep(10)"], ".", "test", timeout=1)
    result = run_gate(tmp_path, gate, timeout=1)
    assert result.category == "timeout"


def test_run_gate_respects_cwd(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.txt").write_text("hi")
    gate = QualityCommand("cat", ["cat", "file.txt"], "sub", "other")
    result = run_gate(tmp_path, gate)
    assert "hi" in result.stdout


# ── run_quality_gates ─────────────────────────────────────

def test_run_quality_gates_discovers_and_runs(tmp_path: Path):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text('{"scripts": {"lint": "echo lint-ok"}}')
    # no backend defaults without services/backend
    result = run_quality_gates(tmp_path)
    assert result["gates_run"] >= 1
    assert result["passed"] >= 1
    assert result["failed"] == 0


def test_run_quality_gates_kind_filter(tmp_path: Path):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text(
        '{"scripts": {"lint": "exit 1", "build": "echo ok"}}'
    )
    result = run_quality_gates(tmp_path, kinds=["lint"])
    assert result["gates_run"] == 1
    assert result["results"][0]["category"] == "code_error"


def test_summarize_renders_lines():
    result = {
        "results": [
            {"name": "pytest", "category": "success", "exit_code": 0},
            {"name": "tsc", "category": "type_error", "exit_code": 2},
        ]
    }
    text = summarize(result)
    assert "PASS" in text and "FAIL(type_error)" in text
