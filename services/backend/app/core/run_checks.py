"""
KUDOS RunChecks — run quality gates and classify failures.

Distinguishes failure categories so the agent can react correctly:

- code_error        — lint violations, syntax problems
- test_failure      — pytest test failures
- type_error        — tsc/mypy type-check errors
- dependency_error  — missing packages/binaries (install failed)
- missing_env       — required environment variables absent
- database_error    — DB connectivity/init failures
- network_error     — network/SSL/registry failures
- timeout           — command exceeded its time budget
- infrastructure    — Docker/service/port failures
- success           — gate passed
"""
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.tooling import QualityCommand, discover_commands, _rl


@dataclass
class GateResult:
    """Outcome of one quality gate."""

    name: str
    kind: str
    category: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.category == "success"

    def summary(self, max_len: int = 200) -> str:
        text = (self.stdout + "\n" + self.stderr).strip()
        return text[:max_len]


def classify(name: str, kind: str, exit_code: int, stdout: str, stderr: str, timed_out: bool) -> str:
    """Map a gate's exit code + output to a failure category.

    Output-signal detection runs first; the kind-based fallbacks only apply
    when the output carries no explicit signal.
    """
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "success"

    combined = f"{stdout}\n{stderr}"
    low = combined.lower()

    if "command not found" in low or "no such file or directory" in low:
        return "dependency_error"
    if "modulenotfounderror" in low or "importerror" in low or "cannot find module" in low:
        return "dependency_error"
    if "environment variable" in low or "env var" in low or "missingenv" in low or "DATABASE_URL" in low:
        return "missing_env"
    if "operationalerror" in low or "connection refused" in low or "sqlite" in low or "psycopg2" in low:
        return "database_error"
    if "ssl" in low or "timed out" in low or "timeout expired" in low:
        return "network_error"
    if "failed to establish a new connection" in low or "temporary failure in name resolution" in low:
        return "network_error"
    if "could not find a version that satisfies" in low or "no matching distribution" in low:
        return "dependency_error"
    if "docker" in low or "container" in low or "daemon" in low:
        return "infrastructure"
    if "error ts" in low or "error: ts" in low:
        return "type_error"
    if "npm error" in low and ("registry" in low or "network" in low or "fetch" in low):
        return "network_error"
    if "failed to compile" in low or "build failed" in low:
        return "code_error"

    # Kind-based fallbacks (no explicit signal in the output)
    if kind == "typecheck":
        return "type_error"
    if kind == "test":
        return "test_failure"
    if kind == "lint":
        return "code_error"
    if kind == "build":
        return "code_error"
    return "code_error"


def run_gate(root: str | Path, gate: QualityCommand, timeout: Optional[int] = None) -> GateResult:
    """Run a single discovered gate inside the project (or workspace) root."""
    root = Path(root).resolve()
    cwd = root / gate.cwd if gate.cwd and gate.cwd != "." else root
    budget = timeout or gate.timeout
    try:
        result = subprocess.run(
            gate.command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=budget,
            preexec_fn=_rl,
            env={**os.environ},
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        result = subprocess.CompletedProcess(gate.command, 124, str(exc), "")
        timed_out = True

    category = classify(
        gate.name, gate.kind, result.returncode, result.stdout or "", result.stderr or "", timed_out
    )
    return GateResult(
        name=gate.name,
        kind=gate.kind,
        category=category,
        exit_code=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        timed_out=timed_out,
    )


def run_quality_gates(
    root: str | Path,
    *,
    kinds: Optional[list[str]] = None,
    include_ci: bool = False,
    timeout: Optional[int] = None,
) -> dict:
    """Run all discovered quality gates and return structured results.

    ``kinds`` filters to e.g. ["lint", "typecheck"]; defaults to all except
    heavy "build" gates (pass include_ci / explicit kinds to run them).
    """
    root = Path(root).resolve()
    commands = discover_commands(root)
    if not include_ci:
        commands = [c for c in commands if not c.framework == "ci"]
    if kinds:
        commands = [c for c in commands if c.kind in kinds]
    if not kinds and commands:
        # default: skip build (slow) unless explicitly requested
        commands = [c for c in commands if c.kind != "build"]

    results = [run_gate(root, gate, timeout=timeout) for gate in commands]
    return {
        "root": str(root),
        "gates_run": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [r.__dict__ for r in results],
    }


def summarize(results: dict) -> str:
    """Human-readable one-line summary of gate results."""
    lines = []
    for r in results.get("results", []):
        status = "PASS" if r["category"] == "success" else f"FAIL({r['category']})"
        lines.append(f"{status:12} {r['name']:24} exit={r['exit_code']}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# PROVIDER-DISABLED MODE CHECK
# ──────────────────────────────────────────────

def provider_disabled_ok(repo_root: str | Path) -> dict:
    """Verify the backend can start without AI provider credentials.

    Simulates provider-disabled mode by clearing provider keys from the
    environment and importing the app; returns {"ok": bool, "detail": str}.
    """
    backend = Path(repo_root).resolve() / "services" / "backend"
    if not backend.exists():
        return {"ok": False, "detail": "no backend dir"}
    py = str(backend / ".venv" / "bin" / "python")
    if not Path(py).exists():
        py = "python3"
    env = {k: v for k, v in os.environ.items() if "OPENAI" not in k and "ANTHROPIC" not in k and "GEMINI" not in k}
    try:
        result = subprocess.run(
            [py, "-c", "from app.main import app; print('APP_OK')"],
            cwd=str(backend),
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
        if "APP_OK" in result.stdout:
            return {"ok": True, "detail": "app imports with providers disabled"}
        return {"ok": False, "detail": result.stderr[-400:]}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)[-400:]}
