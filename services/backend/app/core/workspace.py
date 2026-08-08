"""
KUDOS Workspace — isolated task workspaces backed by git worktrees.

Each agent task runs in its own worktree created from the repository:

- The main working tree is never modified while a task is being tested.
- Resource limits (CPU, memory, file size) and timeouts are enforced on
  every subprocess the agent runs.
- A snapshot (the base commit + status) is recorded before any change, so a
  full rollback is always possible.
- The final patch is generated from the workspace against the base commit.
- The workspace is cleaned up automatically after the task completes.

Workspaces are ephemeral: they live under ``.kudos_workspaces/`` in the
repository and are removed on ``destroy_workspace`` or when the process exits
(see ``cleanup_all``).
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

WORKSPACES_DIR_NAME = ".kudos_workspaces"

# Names / substrings that mark environment variables as secret-bearing.
# They are never inherited by sandbox subprocesses, so an agent task cannot
# exfiltrate backend credentials via `env` / `printenv` / os.environ.
_SECRET_VARS = {"DATABASE_URL", "REDIS_URL", "API_KEYS", "ADMIN_PASSWORD", "ADMIN_EMAIL"}
_SECRET_PATTERNS = ("KEY", "TOKEN", "PASSWORD", "SECRET", "CREDENTIAL")


def _sandbox_env(cwd: str | None = None) -> dict:
    """Environment for sandboxed subprocesses: host env minus secrets.

    When ``cwd`` is given, ``HOME`` is redirected there so ``~`` expansion
    cannot reach host user files (git/user config, ssh keys).
    """
    env = {}
    for name, value in os.environ.items():
        upper = name.upper()
        if upper in _SECRET_VARS or any(p in upper for p in _SECRET_PATTERNS):
            continue
        env[name] = value
    if cwd is not None:
        env["HOME"] = cwd
    return env


class WorkspaceError(RuntimeError):
    """Raised when a workspace operation fails."""


def _limit_resources() -> None:
    """Resource caps inherited by every child process in a workspace.

    CPU seconds, address space, and max file size are bounded so a runaway
    command cannot starve the host. Unix-only; no-op elsewhere.
    """
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (30, 35))
        resource.setrlimit(resource.RLIMIT_AS, (1 * 1024 * 1024 * 1024, 1 * 1024 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (128 * 1024 * 1024, 128 * 1024 * 1024))
    except (ImportError, ValueError, OSError):
        pass


def _run(cwd: Path, args: list[str], timeout: int = 60,
         env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command inside a workspace with limits and a timeout.

    Secrets are always scrubbed from the inherited environment; ``env`` can
    additionally provide a HOME override (see Workspace.run).
    """
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        preexec_fn=_limit_resources,
        env=env if env is not None else _sandbox_env(),
    )


class Workspace:
    """A disposable git worktree for one agent task."""

    def __init__(self, repo_root: str | Path, name: str, base_commit: Optional[str] = None):
        self.repo_root = Path(repo_root).resolve()
        self.name = name
        self.path = self.repo_root / WORKSPACES_DIR_NAME / name
        self.base_commit = base_commit
        self._branch = f"kudos-task/{name}"
        self._created = False

    # ── lifecycle ──────────────────────────────────────────────

    def create(self, *, create_branch: bool = False, force: bool = False) -> "Workspace":
        """Create the worktree.

        By default the worktree is created from ``base_commit`` (or HEAD when
        not given) in a detached state, so the main branch is untouched. With
        ``create_branch=True`` a task branch ``kudos-task/<name>`` is created
        from the base commit.
        """
        if self._created and self.path.exists():
            return self
        if self.path.exists() and not force:
            raise WorkspaceError(f"Workspace already exists: {self.path}")
        if self.path.exists():
            self._remove()
        if self.base_commit is None:
            rc = _run(self.repo_root, ["git", "rev-parse", "HEAD"])
            if rc.returncode != 0:
                raise WorkspaceError(f"Cannot resolve HEAD: {rc.stderr.strip()}")
            self.base_commit = rc.stdout.strip()

        args = ["git", "worktree", "add", "--detach", str(self.path), self.base_commit]
        if create_branch:
            args = ["git", "worktree", "add", "-b", self._branch, str(self.path), self.base_commit]
        result = _run(self.repo_root, args)
        if result.returncode != 0:
            raise WorkspaceError(f"Worktree creation failed: {result.stderr.strip()}")
        self._created = True
        self.snapshot = {"base_commit": self.base_commit, "created_at": self._now()}
        return self

    def destroy(self) -> None:
        """Remove the worktree and its metadata."""
        if not self.path.exists():
            return
        self._remove()
        _run(self.repo_root, ["git", "worktree", "prune"], timeout=30)

    def _remove(self) -> None:
        rc = _run(self.repo_root, ["git", "worktree", "remove", "--force", str(self.path)], timeout=60)
        if rc.returncode != 0:
            # Fallback: delete manually
            shutil.rmtree(self.path, ignore_errors=True)
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *exc) -> None:
        self.destroy()

    # ── git helpers ────────────────────────────────────────────

    def _git(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
        return _run(self.path, ["git"] + args, timeout=timeout)

    def status(self) -> str:
        """Short porcelain status of the workspace."""
        rc = self._git(["status", "--porcelain"])
        return rc.stdout

    def diff_unstaged(self) -> str:
        rc = self._git(["diff"])
        return rc.stdout

    def diff_staged(self) -> str:
        rc = self._git(["diff", "--cached"])
        return rc.stdout

    def patch(self) -> str:
        """Full patch of workspace changes vs the base commit.

        Untracked files are included via intent-to-add so the patch is
        complete (``git diff`` alone skips untracked files).
        """
        rc = self._git(["ls-files", "--others", "--exclude-standard"], timeout=60)
        for name in rc.stdout.splitlines():
            if name.strip():
                self._git(["add", "-N", "--", name.strip()], timeout=30)
        return self._git(["diff", self.base_commit], timeout=120).stdout

    def rollback(self) -> None:
        """Restore the workspace to the base snapshot.

        Discards tracked changes and removes untracked files added by the
        task. The workspace remains usable afterwards.
        """
        self._git(["reset", "--hard", self.base_commit], timeout=120)
        self._git(["clean", "-fd"], timeout=120)

    def run(self, args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
        """Run a command inside the workspace with limits applied.

        The child env is scrubbed of secrets and ``HOME`` is redirected to
        the workspace so ``~``-based lookups cannot reach host files.
        """
        return _run(self.path, args, timeout=timeout, env=_sandbox_env(str(self.path)))

    def files_changed(self) -> list[str]:
        """Names of files modified in the workspace vs the base commit.

        Includes untracked files (task may create new files).
        """
        rc = self._git(["diff", "--name-only", self.base_commit], timeout=60)
        names = [line for line in rc.stdout.splitlines() if line.strip()]
        rc2 = self._git(["ls-files", "--others", "--exclude-standard"], timeout=60)
        names.extend(line for line in rc2.stdout.splitlines() if line.strip())
        return sorted(set(names))

    # ── misc ───────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def __repr__(self) -> str:
        return f"<Workspace {self.name} at {self.path}>"


def cleanup_all(repo_root) -> int:
    """Destroy every worktree under the repo's workspaces dir; returns count."""
    root = Path(repo_root).resolve()
    ws_dir = root / WORKSPACES_DIR_NAME
    if not ws_dir.exists():
        return 0
    removed = 0
    for entry in sorted(ws_dir.iterdir()):
        if entry.is_dir():
            try:
                Workspace(root, entry.name).destroy()
                removed += 1
            except Exception:
                continue
    if removed:
        _run(root, ["git", "worktree", "prune"], timeout=30)
    return removed
