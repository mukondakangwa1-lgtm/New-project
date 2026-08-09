"""Provision backend and storage secrets automatically.

Generates (or repairs) strong random secrets in the backend ``.env`` file so a
fresh checkout can be deployed with zero manual input. Values already present
are never overwritten; placeholder markers are replaced only when the caller
passes ``--replace-placeholders`` (default for CI is to keep them).

Creates:

    SECRET_KEY               app signing key (>= 32 chars)
    POSTGRES_PASSWORD        database password (if missing)
    MINIO_ROOT_USER          MinIO root admin login
    MINIO_ROOT_PASSWORD      MinIO root password (>= 8 chars)
    MINIO_ACCESS_KEY         MinIO application user login (scoped policy)
    MINIO_SECRET_KEY         MinIO application user password
    STORAGE_BACKEND          minio (defaults to auto; set to minio in prod)
    MINIO_ENDPOINT           minio:9000 (compose network)
    MINIO_BUCKET             kudos

Usage:
    python scripts/provision_env.py            # in-place, idempotent
    python scripts/provision_env.py --show      # print effective values (no keys)
    python scripts/provision_env.py --replace-placeholders --show
"""

from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"

# docker-compose interpolation reads a .env next to the compose file (repo
# root). Keep the same credentials in both places so `make deploy` needs no
# manual syncing. Only the keys compose interpolation needs are mirrored.
REPO_ROOT = BACKEND_DIR.parent.parent
COMPOSE_KEYS = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "MINIO_BUCKET",
)
COMPOSE_ENV_PATH = REPO_ROOT / ".env"

PLACEHOLDER_VALUES = {
    "changeme",
    "changeme-in-production",
    "replace-with-a-long-random-password",
    "replace-with-a-random-string-at-least-32-chars",
}


def _random(len_: int = 48) -> str:
    return secrets.token_urlsafe(len_)


def _user(len_: int = 12) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "kudos-" + "".join(secrets.choice(alphabet) for _ in range(len_))


def load_env(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines (later occurrences win; comments ignored)."""
    env: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def provision(
    path: Path = ENV_PATH, replace_placeholders: bool = True
) -> dict[str, str]:
    """Populate ``path`` with missing secrets; returns the final env map."""
    env = load_env(path)
    defined = {
        "SECRET_KEY": lambda: _random(48),
        "POSTGRES_PASSWORD": lambda: _random(40),
        "MINIO_ROOT_USER": lambda: _user(16),
        "MINIO_ROOT_PASSWORD": lambda: _random(32),
        "MINIO_ACCESS_KEY": lambda: _user(24),
        "MINIO_SECRET_KEY": lambda: _random(48),
    }
    postgres_regenerated = False
    for key, generator in defined.items():
        if key not in env or (replace_placeholders and env[key] in PLACEHOLDER_VALUES):
            env[key] = generator()
            if key == "POSTGRES_PASSWORD":
                postgres_regenerated = True

    env.setdefault("MINIO_ENDPOINT", "minio:9000")
    env.setdefault("MINIO_BUCKET", "kudos")
    env.setdefault("STORAGE_BACKEND", "minio")

    # Keep DATABASE_URL in lockstep with the composed Postgres credentials.
    # URLs pointing at the local compose host (db:5432) are rewritten so a
    # freshly provisioned .env never carries a stale password; external or
    # managed databases keep their explicit URLs untouched.
    current_url = env.get("DATABASE_URL", "")
    if "@db:5432/" in current_url or postgres_regenerated or not current_url:
        env["DATABASE_URL"] = (
            f"postgresql://{env.get('POSTGRES_USER', 'dc_user')}:{env['POSTGRES_PASSWORD']}"
            f"@db:5432/{env.get('POSTGRES_DB', 'digital_campus')}"
        )

    path.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(env.items())) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)

    _mirror_compose_env(env)
    return env


def _mirror_compose_env(env: dict[str, str]) -> None:
    """Mirror storage/database credentials into the compose project ``.env``."""
    if not (COMPOSE_ENV_PATH.parent / "docker-compose.yml").is_file():
        return  # running outside the repo (e.g. inside Docker) — skip
    project_env = load_env(COMPOSE_ENV_PATH)
    for key in COMPOSE_KEYS:
        if key in env:
            project_env[key] = env[key]
    if project_env == load_env(COMPOSE_ENV_PATH):
        return
    COMPOSE_ENV_PATH.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(project_env.items()))
        + "\n",
        encoding="utf-8",
    )
    os.chmod(COMPOSE_ENV_PATH, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show", action="store_true", help="print effective vars (no secrets values)"
    )
    parser.add_argument(
        "--replace-placeholders",
        action="store_true",
        help="regenerate values that still look like placeholders",
    )
    args = parser.parse_args()

    env = provision(replace_placeholders=args.replace_placeholders)
    if args.show:
        for key in sorted(env):
            value = env[key]
            if any(secret in key for secret in ("SECRET", "PASSWORD", "KEY")):
                value = "<hidden>"
            print(f"{key}={value}")
    else:
        print(f"provisioned {ENV_PATH} ({len(env)} variables)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
