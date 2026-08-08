#!/usr/bin/env python3
"""
Sync Postgres → SQLite replica for offline use (Pattern B pull).

Usage:
    python scripts/sync_pg_to_sqlite.py --pg-url postgresql+psycopg2://dc_user:dc_pass@localhost:5432/digital_campus --sqlite-path ./digital_campus_local.db
    python scripts/sync_pg_to_sqlite.py --tables users,courses,kudos_documents,kudos_chunks
    python scripts/sync_pg_to_sqlite.py --pg-url $DATABASE_URL --sqlite-path ./local.db --tables all --no-vectors

Notes:
- Requires both DB drivers: psycopg2-binary + aiosqlite/sqlite3 (stdlib).
- Skips kudos_vectors by default with --no-vectors (pgvector has no SQLite equivalent).
- Overwrites SQLite tables (drop+recreate).
"""
import argparse
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.orm import sessionmaker

DEFAULT_TABLES = [
    "users",
    "courses",
    "enrollments",
    "timetable_entries",
    "sessions",
    "posts",
    "comments",
    "kudos_documents",
    "kudos_chunks",
    "kudos_web_knowledge",
    "kudos_connectors",
    "kudos_knowledge_packs",
    "assignments",
    "study_groups",
    "calendar_events",
    "exams",
    "notifications",
]

def sync(pg_url: str, sqlite_path: str, tables: list[str], skip_vectors: bool = True):
    if "kudos_vectors" in tables and skip_vectors:
        print("⚠ Skipping kudos_vectors (pgvector → no SQLite equivalent). Use --no-vectors false to force.")
        tables = [t for t in tables if t != "kudos_vectors"]

    print(f"→ Connecting PG: {pg_url.split('@')[-1]}")
    pg_engine = create_engine(pg_url, pool_pre_ping=True)
    # Ensure sqlite path
    sqlite_url = f"sqlite:///{sqlite_path}"
    print(f"→ Target SQLite: {sqlite_path}")
    lite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    # Reflect PG metadata
    pg_meta = MetaData()
    pg_meta.reflect(bind=pg_engine)

    lite_meta = MetaData()

    for tbl_name in tables:
        if tbl_name not in pg_meta.tables:
            print(f"  ⊘ Table '{tbl_name}' not in Postgres — skipping")
            continue
        pg_table = pg_meta.tables[tbl_name]
        print(f"  ↻ Copying {tbl_name} ({len(pg_table.columns)} cols)...")

        # Recreate in SQLite: reflect column definitions (types auto-adapted)
        # Build new Table in lite_meta from pg_table
        from sqlalchemy import Column
        cols = []
        for c in pg_table.columns:
            # Copy column with same type (SQLAlchemy will adapt PG → SQLite types)
            cols.append(Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable, default=c.default))
        # Clear if exists
        if pg_table.name in lite_meta.tables:
            lite_meta.tables[pg_table.name].drop(lite_engine, checkfirst=True)
        lite_table = Table(pg_table.name, lite_meta, *cols, extend_existing=True)
        lite_table.create(lite_engine, checkfirst=True)

        # Copy rows
        with pg_engine.connect() as pg_conn:
            rows = pg_conn.execute(select(pg_table)).fetchall()
            if not rows:
                print(f"    0 rows")
                continue
            # Insert in batches
            batch = []
            for r in rows:
                batch.append(dict(r._mapping))
            with lite_engine.begin() as lite_conn:
                lite_conn.execute(text(f"DELETE FROM {tbl_name}"))
                lite_conn.execute(lite_table.insert(), batch)
            print(f"    {len(rows)} rows ✓")

        # SQLite pragmas
        with lite_engine.connect() as c:
            c.execute(text("PRAGMA journal_mode=WAL;"))
            c.commit()

    print(f"\n✓ Replica ready: {sqlite_path} ({os.path.getsize(sqlite_path)/1024:.1f} KB)")
    print("  Use with: DATABASE_URL_LOCAL=sqlite:///./digital_campus_local.db")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Postgres → SQLite replica")
    ap.add_argument("--pg-url", default=os.getenv("DATABASE_URL", "postgresql+psycopg2://dc_user:dc_pass@db:5432/digital_campus"))
    ap.add_argument("--sqlite-path", default="./digital_campus_local.db")
    ap.add_argument("--tables", default="all", help="comma-separated or 'all'")
    ap.add_argument("--no-vectors", action="store_true", default=True, help="skip kudos_vectors")
    args = ap.parse_args()

    if args.tables == "all":
        tables = DEFAULT_TABLES
    else:
        tables = [t.strip() for t in args.tables.split(",") if t.strip()]

    # Handle sqlite:///./ prefix
    if args.sqlite_path.startswith("sqlite"):
        args.sqlite_path = args.sqlite_path.split(":///")[-1]

    sync(args.pg_url, args.sqlite_path, tables, skip_vectors=args.no_vectors)
