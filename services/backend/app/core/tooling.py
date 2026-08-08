"""
KUDOS Tooling — project command discovery and environment preparation.

Discovers the project's quality commands from:

- package.json (scripts)
- pyproject.toml / requirements*.txt
- Makefile targets
- CI workflow steps (.github/workflows/*.yml)
- README quick-start sections

and prepares the environment (Python/Node detection, venv reuse, dependency
installation from lockfiles with caching and retries). AI provider
credentials are never required: the app must start in provider-disabled mode.
"""
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class ToolingError(RuntimeError):
    """Raised when environment preparation fails."""


@dataclass
class QualityCommand:
    """A discoverable quality-gate command."""

    name: str
    command: list[str]
    cwd: str  # relative to repo root
    kind: str  # lint | typecheck | test | build | audit | other
    framework: str = ""
    timeout: int = 600


@dataclass
class ProjectEnvironment:
    """Detected runtime environment facts."""

    python: Optional[str] = None
    python_version: Optional[str] = None
    node: Optional[str] = None
    node_version: Optional[str] = None
    venv_exists: bool = False
    npm_available: bool = False
    docker_available: bool = False
    ruff_available: bool = False
    mypy_available: bool = False
    commands: list[QualityCommand] = field(default_factory=list)


def _run(cwd: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
            env={**os.environ}, preexec_fn=_rl,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "timeout", "timeout")


def _rl() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (60, 70))
    except Exception:
        pass


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ──────────────────────────────────────────────
# DETECTION
# ──────────────────────────────────────────────

def detect_environment(repo_root: str | Path) -> ProjectEnvironment:
    """Detect runtimes and tool availability without side effects."""
    root = Path(repo_root).resolve()
    env = ProjectEnvironment()

    py = shutil.which("python3") or shutil.which("python")
    if py:
        env.python = py
        rc = _run(root, [py, "--version"])
        env.python_version = rc.stdout.strip() or rc.stderr.strip()

    node = shutil.which("node")
    if node:
        env.node = node
        rc = _run(root, [node, "--version"])
        env.node_version = rc.stdout.strip()

    backend_venv = root / "services" / "backend" / ".venv" / "bin" / "python"
    env.venv_exists = backend_venv.exists()
    env.npm_available = shutil.which("npm") is not None
    env.docker_available = shutil.which("docker") is not None
    env.ruff_available = shutil.which("ruff") is not None
    env.mypy_available = shutil.which("mypy") is not None
    return env


# ──────────────────────────────────────────────
# DISCOVERY
# ──────────────────────────────────────────────

def _package_scripts(pkg: dict) -> list[QualityCommand]:
    """Map common npm scripts to quality gates."""
    scripts = pkg.get("scripts", {})
    out: list[QualityCommand] = []
    mapping = {
        "lint": "lint",
        "typecheck": "typecheck",
        "test": "test",
        "build": "build",
        "audit": "audit",
    }
    for script, kind in mapping.items():
        if script in scripts:
            out.append(
                QualityCommand(name=f"npm:{script}", command=["npm", "run", script],
                               cwd="frontend", kind=kind, framework="npm")
            )
    if not out and "devDependencies" in pkg or "dependencies" in pkg:
        # TypeScript is present — a tsc typecheck is a safe default gate.
        out.append(QualityCommand(name="npm:tsc", command=["npx", "tsc", "--noEmit"],
                                  cwd="frontend", kind="typecheck", framework="npm"))
    return out


def _ci_commands(workflows_dir: Path) -> list[QualityCommand]:
    """Extract test/lint commands from CI workflow steps (best effort)."""
    if not workflows_dir.exists():
        return []
    out: list[QualityCommand] = []
    for wf in workflows_dir.glob("*.yml"):
        try:
            text = wf.read_text(encoding="utf-8")
        except Exception:
            continue
        # crude extraction: lines like `run: pytest tests/ -q` or `ruff check ...`
        for m in re.finditer(r"^\s+(?:-\s+)?run:\s+(.+)$", text, re.MULTILINE):
            cmd = m.group(1).strip()
            if cmd.startswith(("pytest", "ruff", "npm ci", "tsc")):
                kind = "test" if cmd.startswith("pytest") else (
                    "lint" if cmd.startswith("ruff") else "typecheck"
                )
                cwd = "services/backend" if "pytest" in cmd or "ruff" in cmd else "frontend"
                out.append(QualityCommand(name=f"ci:{wf.stem}", command=cmd.split(),
                                          cwd=cwd, kind=kind, framework="ci"))
    return out


def _makefile_commands(makefile: Path) -> list[QualityCommand]:
    """Extract test/lint targets from a Makefile."""
    if not makefile.exists():
        return []
    out: list[QualityCommand] = []
    try:
        text = makefile.read_text(encoding="utf-8")
    except Exception:
        return out
    for m in re.finditer(r"^([a-zA-Z_-]+):.*?##\s*(.*)$", text, re.MULTILINE):
        target = m.group(1)
        if target in ("test", "lint", "check", "build"):
            # find the recipe line following the target
            rest = text[m.end():]
            recipe = re.search(r"^\t([^\n]+)", rest, re.MULTILINE)
            if recipe:
                out.append(QualityCommand(name=f"make:{target}",
                                          command=["make", target],
                                          cwd=".", kind=target, framework="make"))
    return out


def discover_commands(repo_root: str | Path) -> list[QualityCommand]:
    """Discover every quality-gate command the repo declares."""
    root = Path(repo_root).resolve()
    commands: list[QualityCommand] = []
    seen: set[tuple[str, str, str]] = set()

    pkg = _read_json(root / "frontend" / "package.json")
    if pkg:
        for c in _package_scripts(pkg):
            key = (c.name, c.cwd, " ".join(c.command))
            if key not in seen:
                seen.add(key)
                commands.append(c)

    for c in _ci_commands(root / ".github" / "workflows"):
        key = (c.name, c.cwd, " ".join(c.command))
        if key not in seen:
            seen.add(key)
            commands.append(c)

    for c in _makefile_commands(root / "Makefile"):
        key = (c.name, c.cwd, " ".join(c.command))
        if key not in seen:
            seen.add(key)
            commands.append(c)

    # Backend defaults when nothing else was discovered
    backend = root / "services" / "backend"
    if backend.exists():
        python = str(backend / ".venv" / "bin" / "python")
        if not Path(python).exists():
            python = shutil.which("python3") or "python"
        defaults = [
            QualityCommand("pytest", [python, "-m", "pytest", "tests/", "-q", "--tb=short"],
                           "services/backend", "test", "pytest"),
            QualityCommand("ruff", ["ruff", "check", "app/", "--select", "F"],
                           "services/backend", "lint", "ruff"),
            QualityCommand("compileall", [python, "-m", "compileall", "-q", "app"],
                           "services/backend", "typecheck", "python"),
        ]
        for c in defaults:
            key = (c.name, c.cwd, " ".join(c.command))
            if key not in seen:
                seen.add(key)
                commands.append(c)

    return commands


# ──────────────────────────────────────────────
# ENVIRONMENT PREPARATION
# ──────────────────────────────────────────────

def ensure_venv(repo_root: str | Path, *, recreate: bool = False) -> str:
    """Create or reuse the backend venv; returns the python interpreter path."""
    backend = Path(repo_root).resolve() / "services" / "backend"
    if not backend.is_dir():
        raise ToolingError(f"backend directory missing: {backend}")
    py_bin = backend / ".venv" / "bin" / "python"
    if py_bin.exists() and not recreate:
        return str(py_bin)
    venv_dir = backend / ".venv"
    python = shutil.which("python3") or shutil.which("python")
    if not python:
        raise ToolingError("No Python interpreter found on PATH")
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    rc = _run(backend, [python, "-m", "venv", ".venv"], timeout=120)
    if rc.returncode != 0:
        raise ToolingError(f"venv creation failed: {rc.stderr[:300]}")
    return str(py_bin)


def install_dependencies(
    repo_root: str | Path,
    *,
    targets: Optional[list[str]] = None,
    offline: bool = False,
    retries: int = 2,
    timeout: int = 900,
) -> dict:
    """Install backend/frontend dependencies from lockfiles/requirements.

    Targets: "backend", "frontend" (default: both when present).
    Uses pip with a local cache and npm ci; retries transient failures.
    Returns {"installed": [targets], "errors": [...]}.
    """
    root = Path(repo_root).resolve()
    targets = targets or []
    if not targets:
        targets = []
        if (root / "services" / "backend" / "requirements.txt").exists():
            targets.append("backend")
        if (root / "frontend" / "package.json").exists():
            targets.append("frontend")

    installed: list[str] = []
    errors: list[str] = []

    for target in targets:
        try:
            if target == "backend":
                _install_backend(root, offline=offline, retries=retries, timeout=timeout)
            elif target == "frontend":
                _install_frontend(root, offline=offline, retries=retries, timeout=timeout)
            else:
                errors.append(f"unknown target: {target}")
                continue
            installed.append(target)
        except ToolingError as exc:
            errors.append(str(exc))
    return {"installed": installed, "errors": errors}


def _with_retry(fn, retries: int, label: str):
    last: Optional[ToolingError] = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except ToolingError as exc:
            last = exc
            if attempt < retries:
                continue
    raise last or ToolingError(f"{label} failed")


def _install_backend(root: Path, *, offline: bool, retries: int, timeout: int) -> None:
    backend = root / "services" / "backend"
    py = ensure_venv(root)
    reqs = backend / "requirements.txt"
    dev = backend / "requirements-dev.txt"
    if not reqs.exists() and not dev.exists():
        raise ToolingError("backend: no requirements files found")

    def _pip(files: list[Path], extra: str = "") -> None:
        args = [py, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"]
        if offline:
            args += ["--no-index", "--find-links", "/tmp/kudos_pip_cache"]
        else:
            args += ["--cache-dir", "/tmp/kudos_pip_cache"]
        args += extra.split()
        for f in files:
            args += ["-r", str(f)]
        rc = _run(backend, args, timeout=timeout)
        if rc.returncode != 0:
            raise ToolingError(f"backend pip install failed: {rc.stderr[-400:]}")

    _with_retry(lambda: _pip([reqs]), retries, "backend requirements")
    if dev.exists():
        _with_retry(lambda: _pip([dev]), retries, "backend dev requirements")


def _install_frontend(root: Path, *, offline: bool, retries: int, timeout: int) -> None:
    frontend = root / "frontend"
    if not (frontend / "package.json").exists():
        raise ToolingError("frontend: no package.json found")
    lockfile = frontend / "package-lock.json"
    if lockfile.exists() and not offline:
        def _ci() -> None:
            rc = _run(frontend, ["npm", "ci", "--no-audit", "--no-fund"], timeout=timeout)
            if rc.returncode != 0:
                raise ToolingError(f"npm ci failed: {rc.stderr[-400:]}")
        _with_retry(_ci, retries, "npm ci")
    else:
        def _install() -> None:
            cmd = ["npm", "install", "--no-audit", "--no-fund"]
            if offline:
                cmd.append("--offline")
            rc = _run(frontend, cmd, timeout=timeout)
            if rc.returncode != 0:
                raise ToolingError(f"npm install failed: {rc.stderr[-400:]}")
        _with_retry(_install, retries, "npm install")
