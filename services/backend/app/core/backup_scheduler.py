"""Self-contained backup scheduler for the compose deployment.

Runs a PostgreSQL dump + prune every 24h (02:00 UTC by default) instead of
relying on a host cron, so the whole deployment stays inside the compose
swarm. Verifies the scheduler works with ``--once``.

Usage:
    python -m app.core.backup_scheduler           # loop (compose)
    python -m app.core.backup_scheduler --once    # single run + exit
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta

from app.core import backup

DEFAULT_HOUR = int(os.environ.get("BACKUP_HOUR", "2"))  # UTC hour of day


def run_once() -> None:
    """One backup cycle: dump Postgres (or SQLite) then prune old copies."""
    mode = "sqlite" if _sqlite_url() else "postgres"
    if mode == "sqlite":
        backup.sqlite_dump()
    else:
        backup.dump()
    removed = backup.prune_backups()
    print(f"[{datetime.now(UTC).isoformat()}] {mode} backup ok; pruned {len(removed)} old")


def _sqlite_url() -> bool:
    return backup.settings.DATABASE_URL.startswith("sqlite")


def _next_fire(now: datetime, hour: int) -> datetime:
    """Next occurrence of ``hour`` UTC on or after ``now``."""
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run a single backup and exit")
    args = parser.parse_args()

    hour = DEFAULT_HOUR
    if args.once:
        try:
            run_once()
        except Exception as exc:
            print(f"backup failed: {exc}", file=sys.stderr)
            return 1
        return 0

    print(f"scheduler started — daily {hour:02d}:00 UTC", flush=True)
    while True:
        now = datetime.now(UTC)
        target = _next_fire(now, hour)
        time.sleep(max(0, int((target - now).total_seconds())))
        try:
            run_once()
        except Exception as exc:
            print(f"backup failed, will retry tomorrow: {exc}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
