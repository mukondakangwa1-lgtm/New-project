"""PostgreSQL backup/restore helpers for the Digital Campus backend.

Uses ``pg_dump`` / ``pg_restore`` from the system PATH. Works on the
``DATABASE_URL`` from settings; refuses SQLite databases. Provides a small CLI:

    python -m app.core.backup dump
    python -m app.core.backup restore backups/digital_campus_20260101_120000.dump
    python -m app.core.backup prune
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from typing import List

from app.core.config import settings


def backup_dir() -> str:
    return os.path.abspath(settings.BACKUP_DIR)


def dump_filename(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"digital_campus_{now.strftime('%Y%m%d_%H%M%S')}.dump"


def ensure_backup_dir() -> str:
    path = backup_dir()
    os.makedirs(path, exist_ok=True)
    return path


def _pg_cmd(url: str, which: str) -> List[str]:
    """Build env-driven pg_dump/pg_restore invocation pieces."""
    if url.startswith("sqlite"):
        raise ValueError("Backup/restore requires PostgreSQL (DATABASE_URL)")
    return [which, "--dbname", url, "--no-owner", "--no-privileges"]


def dump(database_url: str | None = None) -> str:
    """Create a compressed custom-format dump and return its path."""
    url = database_url or settings.DATABASE_URL
    dest = os.path.join(ensure_backup_dir(), dump_filename())
    cmd = _pg_cmd(url, "pg_dump") + ["-F", "c", "-f", dest]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    return dest


def restore(dump_path: str, database_url: str | None = None) -> None:
    """Restore a custom-format dump into the target database."""
    url = database_url or settings.DATABASE_URL
    if not os.path.isfile(dump_path):
        raise FileNotFoundError(f"backup file not found: {dump_path}")
    cmd = ["pg_restore", "--dbname", url, "--no-owner", "--no-privileges", dump_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=900)


def list_backups() -> List[str]:
    path = backup_dir()
    if not os.path.isdir(path):
        return []
    return sorted(
        (os.path.join(path, name) for name in os.listdir(path) if name.endswith(".dump")),
        reverse=True,
    )


def prune_backups(keep: int | None = None) -> List[str]:
    """Remove oldest dumps beyond ``keep``; return the removed paths."""
    keep = keep or settings.BACKUP_KEEP
    backups = list_backups()
    removed = []
    for old in backups[keep:]:
        os.remove(old)
        removed.append(old)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Digital Campus PostgreSQL backup tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dump", help="create a custom-format dump")
    restore_p = sub.add_parser("restore", help="restore a dump")
    restore_p.add_argument("file", help="path to the .dump file")
    sub.add_parser("prune", help="remove old dumps beyond BACKUP_KEEP")
    args = parser.parse_args()

    try:
        if args.command == "dump":
            os.makedirs(backup_dir(), exist_ok=True)
            path = dump()
            print(f"backup written to {path}")
        elif args.command == "restore":
            restore(args.file)
            print(f"restored {args.file}")
        elif args.command == "prune":
            removed = prune_backups()
            print(f"removed {len(removed)} old backups")
        return 0
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"backup error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())