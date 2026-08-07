"""Filesystem roots that work both from a source checkout and in Docker."""

from __future__ import annotations

from pathlib import Path


def backend_root(current_file: str | Path) -> Path:
    """Locate the backend root containing ``app/`` and ``requirements.txt``."""
    path = Path(current_file).resolve()
    for candidate in (path, *path.parents):
        if (candidate / "app").is_dir() and (candidate / "requirements.txt").is_file():
            return candidate
    return path.parent


def project_root(current_file: str | Path) -> Path:
    """Locate the monorepo root, falling back to the Docker backend root."""
    backend = backend_root(current_file)
    for candidate in (backend, *backend.parents):
        if (candidate / "docker-compose.yml").is_file():
            return candidate
    return backend
