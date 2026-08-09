"""
KUDOS GitOps — safe git and pull-request workflow.

Rules enforced here:

- Refuse to modify protected branches (main, master, develop) without
  explicit approval.
- Stage only an explicit allowlist of files — never ``git add -A``.
- Detect unrelated changes in the working tree and preserve them.
- Show staged and unstaged diffs separately.
- Fetch remote metadata before starting; detect conflicts before pushing.
- Never force-push by default.
- Push and pull-request creation require separate approval.
"""
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.pathguard import PathError, resolve_inside

PROTECTED_BRANCHES = frozenset({"main", "master", "develop"})


class GitOpsError(RuntimeError):
    """Raised when a git operation is not permitted or fails."""


@dataclass
class RepoState:
    branch: str
    protected: bool
    staged: list[str] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    has_remote: bool = False

    @property
    def dirty(self) -> bool:
        return bool(self.staged or self.unstaged or self.untracked)

    def unrelated_changes(self, task_files: list[str]) -> list[str]:
        """Changes in the tree that are not part of the task."""
        allowed = set(task_files)
        all_changes = set(self.staged) | set(self.unstaged) | set(self.untracked)
        return sorted(all_changes - allowed)


def _run(repo: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ},
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(["git"] + args, 124, "", "timeout")


def _lines(out: str) -> list[str]:
    return [l for l in out.splitlines() if l.strip()]


def current_branch(repo: Path) -> str:
    rc = _run(repo, ["branch", "--show-current"])
    return rc.stdout.strip()


def fetch_remote(repo: Path) -> dict:
    """Fetch remote metadata (best effort). Returns remote name or None."""
    rc = _run(repo, ["remote"])
    remotes = _lines(rc.stdout)
    if not remotes:
        return {"fetched": False, "remote": None, "reason": "no remotes configured"}
    name = remotes[0]
    rc = _run(repo, ["fetch", name], timeout=120)
    return {
        "fetched": rc.returncode == 0,
        "remote": name,
        "reason": "" if rc.returncode == 0 else rc.stderr[:200],
    }


def repo_state(repo: Path, *, fetch: bool = False) -> RepoState:
    """Snapshot the repository state: branch, protection, changes."""
    branch = current_branch(repo)
    state = RepoState(branch=branch, protected=branch in PROTECTED_BRANCHES)
    if fetch:
        fetch_remote(repo)
    rc = _run(repo, ["status", "--porcelain=v1"])
    for line in _lines(rc.stdout):
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:]
        if code == "??":
            state.untracked.append(path)
            continue
        if code[0] != " ":
            state.staged.append(path)
        if code[1] != " ":
            state.unstaged.append(path)
    state.has_remote = bool(_run(repo, ["remote"]).stdout.strip())
    return state


def assert_task_branch(repo: Path, *, approval: bool = False) -> RepoState:
    """Ensure the current branch may be modified.

    Protected branches require explicit approval; otherwise raises
    GitOpsError. Returns the repo state.
    """
    state = repo_state(repo)
    if state.protected and not approval:
        raise GitOpsError(
            f"Branch '{state.branch}' is protected. Refusing to modify it "
            "without explicit approval."
        )
    return state


def create_task_branch(repo: Path, task_name: str, base: str = "HEAD") -> str:
    """Create (or reuse) a task branch ``kudos-task/<task_name>``.

    Branching off a protected branch is allowed (it does not modify it), but
    the tree must be clean so unrelated work is never carried over.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_name):
        raise GitOpsError("Invalid task name (letters, digits, - and _ only)")
    branch = f"kudos-task/{task_name}"
    rc = _run(repo, ["rev-parse", "--verify", "--quiet", branch])
    if rc.returncode == 0:
        return branch  # exists already
    state = repo_state(repo)
    if state.dirty:
        raise GitOpsError(
            "Working tree is dirty; refusing to branch from an unclean state. "
            "Commit or stash your unrelated changes first."
        )
    rc = _run(repo, ["checkout", "-b", branch, base])
    if rc.returncode != 0:
        raise GitOpsError(f"Cannot create branch: {rc.stderr[:200]}")
    return branch


def stage_files(repo: Path, files: list[str], *, repo_root: Path) -> dict:
    """Stage an explicit allowlist of files.

    Validates each path with PathGuard and refuses protected files.
    """
    if not files:
        raise GitOpsError("No files to stage")
    resolved = []
    for rel in files:
        try:
            resolve_inside(repo_root, rel, allow_missing=True)
        except PathError as exc:
            raise GitOpsError(f"Refusing to stage: {exc}")
        resolved.append(rel)
    rc = _run(repo, ["add", "--", *resolved])
    if rc.returncode != 0:
        raise GitOpsError(f"git add failed: {rc.stderr[:300]}")
    return {"staged": resolved}


def diff_sections(repo: Path) -> dict:
    """Staged and unstaged diffs separately."""
    staged = _run(repo, ["diff", "--cached"])
    unstaged = _run(repo, ["diff"])
    return {"staged": staged.stdout, "unstaged": unstaged.stdout}


def commit(repo: Path, message: str, files: list[str], *, repo_root: Path) -> dict:
    """Stage the allowlist and commit on the current (task) branch."""
    assert_task_branch(repo)
    stage_files(repo, files, repo_root=repo_root)
    rc = _run(repo, ["commit", "-m", message])
    if rc.returncode != 0:
        out = rc.stdout + rc.stderr
        if "nothing to commit" in out or "no changes added" in out:
            raise GitOpsError("Nothing to commit — no staged changes")
        raise GitOpsError(f"Commit failed: {out[:300]}")
    hash_rc = _run(repo, ["rev-parse", "HEAD"])
    return {"committed": hash_rc.stdout.strip(), "branch": current_branch(repo)}


def detect_conflicts(repo: Path, remote_branch: Optional[str] = None) -> dict:
    """Detect conflicts with the remote before pushing.

    Fetches and uses ``git merge-tree`` on the merge base to find conflicts.
    """
    if not remote_branch:
        rc = _run(repo, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
        if rc.returncode != 0:
            return {"conflicts": [], "checked": False, "reason": "no upstream configured"}
        remote_branch = rc.stdout.strip()
    fetch_remote(repo)
    local = current_branch(repo)
    rc = _run(repo, ["merge-base", local, remote_branch], timeout=60)
    if rc.returncode != 0:
        return {"conflicts": [], "checked": False, "reason": "no common base"}
    base = rc.stdout.strip()
    rc = _run(
        repo,
        ["merge-tree", "--write-tree", base, local, remote_branch],
        timeout=120,
    )
    conflicts = []
    if rc.returncode != 0:
        for line in rc.stdout.splitlines():
            if "conflict" in line.lower():
                conflicts.append(line.strip())
    return {
        "conflicts": conflicts,
        "checked": True,
        "base": base[:8],
        "remote_branch": remote_branch,
    }


def push(repo: Path, *, approved: bool = False, force: bool = False) -> dict:
    """Push the current branch to origin.

    Requires approval; never force-pushes unless explicitly approved.
    """
    if not approved:
        raise GitOpsError("Push requires explicit approval")
    if force and not approved:
        raise GitOpsError("Force push requires explicit approval")
    branch = current_branch(repo)
    args = ["push", "origin", branch]
    if force:
        args.append("--force-with-lease")
    rc = _run(repo, args, timeout=120)
    if rc.returncode != 0:
        raise GitOpsError(f"Push failed: {(rc.stderr or rc.stdout)[:300]}")
    return {"pushed": True, "branch": branch}


def create_pull_request(
    repo: Path,
    title: str,
    body: str,
    *,
    approved: bool = False,
    base: str = "main",
) -> dict:
    """Create a pull request via the ``gh`` CLI (requires approval)."""
    if not approved:
        raise GitOpsError("Pull-request creation requires explicit approval")
    if not repo_state(repo).has_remote:
        raise GitOpsError("No git remote configured")
    branch = current_branch(repo)
    if branch in PROTECTED_BRANCHES:
        raise GitOpsError("Cannot open a PR for a protected branch")
    if not _have_gh():
        return {
            "created": False,
            "reason": "gh CLI not installed — push the branch and open the PR manually",
            "branch": branch,
        }
    rc = _run(
        repo,
        ["gh", "pr", "create", "--base", base, "--head", branch,
         "--title", title, "--body", body],
        timeout=120,
    )
    if rc.returncode != 0:
        raise GitOpsError(f"PR creation failed: {(rc.stderr or rc.stdout)[:300]}")
    return {"created": True, "url": rc.stdout.strip(), "branch": branch}


def _have_gh() -> bool:
    import shutil

    return shutil.which("gh") is not None


def task_branch_safe(repo: Path) -> bool:
    """True when the current branch is safe for agent work."""
    return current_branch(repo) not in PROTECTED_BRANCHES
