"""PostgreSQL backup/restore helpers for the Digital Campus backend.

Uses ``pg_dump`` / ``pg_restore`` from the system PATH for PostgreSQL, and the
``sqlite3`` stdlib for standalone SQLite boxes. Provides a small CLI:

    python -m app.core.backup dump
    python -m app.core.backup restore backups/digital_campus_20260101_120000.dump
    python -m app.core.backup sqlite-dump
    python -m app.core.backup prune
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime

from app.core import storage
from app.core.config import settings

BACKUPS_PREFIX = "backups/"


def backup_dir() -> str:
    return os.path.abspath(settings.BACKUP_DIR)


def dump_filename(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"digital_campus_{now.strftime('%Y%m%d_%H%M%S')}.dump"


def ensure_backup_dir() -> str:
    path = backup_dir()
    os.makedirs(path, exist_ok=True)
    return path


def _pg_cmd(url: str, which: str) -> list[str]:
    """Build env-driven pg_dump/pg_restore invocation pieces."""
    if url.startswith("sqlite"):
        raise ValueError("Backup/restore requires PostgreSQL (DATABASE_URL)")
    return [which, "--dbname", url, "--no-owner", "--no-privileges"]


def dump(database_url: str | None = None) -> str:
    """Create a compressed custom-format dump and return its path.

    The dump is uploaded to object storage (``backups/`` prefix) whenever the
    MinIO backend is active; the local file is kept so the CLI remains useful
    on plain-disk deployments. A MinIO failure never fails the backup itself —
    the local dump is the source of truth.
    """
    url = database_url or settings.DATABASE_URL
    dest = os.path.join(ensure_backup_dir(), dump_filename())
    cmd = [*_pg_cmd(url, "pg_dump"), "-F", "c", "-f", dest]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    if storage.backend_name() == "minio":
        try:
            with open(dest, "rb") as fh:
                storage.upload_bytes(
                    BACKUPS_PREFIX + os.path.basename(dest),
                    fh.read(),
                    content_type="application/octet-stream",
                )
        except Exception:
            print("warning: dump written locally but MinIO upload failed", file=sys.stderr)
    return dest


def restore(dump_path: str, database_url: str | None = None) -> None:
    """Restore a custom-format dump into the target database."""
    url = database_url or settings.DATABASE_URL
    if not os.path.isfile(dump_path):
        raise FileNotFoundError(f"backup file not found: {dump_path}")
    cmd = ["pg_restore", "--dbname", url, "--no-owner", "--no-privileges", dump_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=900)


def list_backups() -> list[str]:
    path = backup_dir()
    if not os.path.isdir(path):
        return []
    return sorted(
        (os.path.join(path, name) for name in os.listdir(path) if name.endswith(".dump")),
        reverse=True,
    )


def prune_backups(keep: int | None = None) -> list[str]:
    """Remove oldest dumps beyond ``keep``; return the removed paths."""
    keep = keep or settings.BACKUP_KEEP
    backups = list_backups()
    removed = []
    for old in backups[keep:]:
        os.remove(old)
        removed.append(old)
    _prune_remote(keep)
    return removed


def _prune_remote(keep: int) -> None:
    """Remove stale dumps from MinIO when the object backend is active."""
    if storage.backend_name() != "minio":
        return
    try:
        from minio import Minio

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        names = sorted(
            obj.object_name for obj in client.list_objects(settings.MINIO_BUCKET, prefix=BACKUPS_PREFIX, recursive=True)
        )
        for old in names[:-keep] if keep else []:
            client.remove_object(settings.MINIO_BUCKET, old)
    except Exception:
        return


def sqlite_dump(database_url: str | None = None) -> str:
    """Online backup of a SQLite database via the stdlib ``backup`` API.

    Used on standalone/dev boxes that run SQLite instead of Postgres. The
    resulting ``.sqlite3`` snapshot is pushed to object storage (``backups/``
    prefix) when MinIO is active, mirroring the PostgreSQL flow.
    """
    url = database_url or settings.DATABASE_URL
    if not url.startswith("sqlite"):
        raise ValueError("sqlite-dump requires a sqlite:/// DATABASE_URL")

    path = url.replace("sqlite:///", "")
    dest = os.path.join(ensure_backup_dir(), dump_filename().replace(".dump", ".sqlite3"))

    source = sqlite3.connect(path)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    if storage.backend_name() == "minio":
        try:
            with open(dest, "rb") as fh:
                storage.upload_bytes(
                    BACKUPS_PREFIX + os.path.basename(dest),
                    fh.read(),
                    content_type="application/octet-stream",
                )
        except Exception:
            print("warning: sqlite dump written locally but MinIO upload failed", file=sys.stderr)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Digital Campus backup tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dump", help="create a PostgreSQL custom-format dump")
    sub.add_parser("sqlite-dump", help="snapshot a SQLite database via the backup API")
    restore_p = sub.add_parser("restore", help="restore a PostgreSQL dump")
    restore_p.add_argument("file", help="path to the .dump file")
    sub.add_parser("prune", help="remove old dumps beyond BACKUP_KEEP")
    args = parser.parse_args()

    try:
        if args.command == "dump":
            os.makedirs(backup_dir(), exist_ok=True)
            path = dump()
            print(f"backup written to {path}")
        elif args.command == "sqlite-dump":
            os.makedirs(backup_dir(), exist_ok=True)
            path = sqlite_dump()
            print(f"sqlite backup written to {path}")
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
