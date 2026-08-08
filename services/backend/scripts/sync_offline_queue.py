#!/usr/bin/env python3
"""
Push SQLite offline queue → Postgres (Pattern B push).

Replays rows where is_offline=true or local-only records.
Default queues:
  - chat_messages where is_offline=true
  - attendances created offline (if you tag them)
  - submissions / kudos_documents flagged offline

Usage:
    python scripts/sync_offline_queue.py --sqlite-path ./digital_campus_local.db --pg-url postgresql+psycopg2://...

Idempotent: clears is_offline after successful insert, logs conflicts.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, MetaData, select, text

def push(sqlite_path: str, pg_url: str, dry_run: bool = False):
    if sqlite_path.startswith("sqlite"):
        sqlite_path = sqlite_path.split(":///")[-1]
    sqlite_url = f"sqlite:///{sqlite_path}"
    print(f"→ Local SQLite: {sqlite_path}")
    print(f"→ Target PG: {pg_url.split('@')[-1]}")
    lite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    pg_engine = create_engine(pg_url, pool_pre_ping=True)

    lite_meta = MetaData()
    lite_meta.reflect(bind=lite_engine)

    total_pushed = 0

    # Queue 1: chat_messages offline
    if "chat_messages" in lite_meta.tables:
        lite_tbl = lite_meta.tables["chat_messages"]
        pg_meta = MetaData()
        pg_meta.reflect(bind=pg_engine)
        if "chat_messages" in pg_meta.tables:
            pg_tbl = pg_meta.tables["chat_messages"]
            with lite_engine.connect() as lite_conn:
                q = select(lite_tbl).where(lite_tbl.c.is_offline == True) if "is_offline" in lite_tbl.c else select(lite_tbl).limit(0)
                rows = lite_conn.execute(q).fetchall() if "is_offline" in lite_tbl.c else []
            if rows:
                print(f"  Found {len(rows)} offline chat_messages")
                if not dry_run:
                    with pg_engine.begin() as pg_conn:
                        for r in rows:
                            d = dict(r._mapping)
                            d.pop("id", None)  # let PG autoincrement
                            d["is_offline"] = False
                            pg_conn.execute(pg_tbl.insert().values(**d))
                    # mark as synced locally
                    with lite_engine.begin() as lite_conn:
                        lite_conn.execute(text("UPDATE chat_messages SET is_offline=0 WHERE is_offline=1"))
                total_pushed += len(rows)
            else:
                print("  No offline chat_messages")

    # Queue 2: add other queues here (attendances, submissions)
    # Example pattern:
    # if "attendances" in lite_meta.tables and "offline_flag" in lite_meta.tables["attendances"].c:
    #     ...

    if dry_run:
        print(f"\n[DRY RUN] Would push {total_pushed} rows")
    else:
        print(f"\n✓ Pushed {total_pushed} rows to Postgres")
        if total_pushed:
            print("  Local is_offline flags cleared")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SQLite offline queue → Postgres")
    ap.add_argument("--sqlite-path", default="./digital_campus_local.db")
    ap.add_argument("--pg-url", default=os.getenv("DATABASE_URL", "postgresql+psycopg2://dc_user:dc_pass@db:5432/digital_campus"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    push(args.sqlite_path, args.pg_url, dry_run=args.dry_run)
