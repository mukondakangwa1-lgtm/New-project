"""
KUDOS PathGuard — safe path handling for agent file operations.

Every file path the agent touches must be validated:

1. Resolved to an absolute path.
2. Confirmed to be inside the isolated workspace.
3. Rejects ``../`` traversal.
4. Rejects symlink escapes (a symlink inside the workspace that points
   outside is not writable through the agent).
5. Rejects writes to protected files unless explicitly approved.
6. Rejects writes to credential stores, SSH keys, and system paths.

Example paths that are always rejected:

    ../../.env
    /etc/passwd
    /root/.ssh/id_rsa
"""

import os
from pathlib import Path


class PathError(ValueError):
    """Raised when a path fails validation."""


# Files that must never be written by the agent unless explicitly approved.
PROTECTED_NAMES = {
    ".env",
    ".env.example",
    "id_rsa",
    "id_rsa.pub",
    "id_ed25519",
    "id_ed25519.pub",
    ".netrc",
    ".pgpass",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "service_account.json",
    "docker_credentials.json",
    ".htpasswd",
}

PROTECTED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore", ".jks")

PROTECTED_PREFIXES = ("/etc/", "/root/", "/home/", "/usr/", "/var/", "/proc/", "/sys/", "/dev/")


def _is_protected_name(name: str) -> bool:
    if name in PROTECTED_NAMES:
        return True
    if name.startswith((".env.", ".env-")):
        return True
    if name.startswith(".git"):
        return True
    return any(name.endswith(suffix) for suffix in PROTECTED_SUFFIXES)


def _is_protected_path(path: Path) -> bool:
    """Check any path component (including the target) for protected names."""
    return any(_is_protected_name(part) for part in path.parts)


def is_inside(root: Path, path: Path) -> bool:
    """True if ``path`` (resolved) is inside ``root`` (resolved)."""
    root_res = root.resolve()
    path_res = path.resolve()
    try:
        return os.path.commonpath([str(root_res), str(path_res)]) == str(root_res)
    except ValueError:
        # Different drives / relative mismatch
        return False


def resolve_inside(workspace_root, relpath: str, *, allow_missing: bool = False) -> Path:
    """Resolve ``relpath`` against the workspace and validate it.

    Steps:

    - The path must be relative (or a resolved absolute path that points
      inside the workspace).
    - ``..`` traversal is rejected by realpath resolution + containment.
    - Symlink escapes are rejected: after ``resolve()`` the target must still
      be inside the workspace.
    - Protected names (credentials, keys, git metadata) are rejected.
    - System paths are rejected by the containment rule anyway.

    Returns the absolute validated path.
    """
    root = Path(workspace_root).resolve()
    raw = Path(str(relpath))
    candidate = root / raw if not raw.is_absolute() else raw
    resolved = candidate.resolve(strict=False) if allow_missing else candidate.resolve()

    if not is_inside(root, candidate):
        raise PathError(f"Path escapes workspace: {relpath}")
    if not is_inside(root, resolved):
        raise PathError(f"Path resolves outside workspace (symlink escape): {relpath}")
    if _is_protected_path(resolved):
        raise PathError(f"Path targets a protected file: {relpath}")
    return resolved


def validate_absolute(path) -> Path:
    """Validate an absolute path the agent wants to read/write.

    Rejects paths outside the allowed roots (system dirs, home dirs, etc.)
    even before workspace containment is checked, for defense in depth.
    """
    p = Path(str(path)).resolve()
    if _is_protected_path(p):
        raise PathError(f"Protected file: {p}")
    low = str(p).lower()
    for prefix in PROTECTED_PREFIXES:
        if low.startswith(prefix):
            raise PathError(f"System path not allowed: {p}")
    return p
