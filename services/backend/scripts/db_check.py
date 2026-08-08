#!/usr/bin/env python3
"""
DB Connection Checker — Works for BOTH PostgreSQL and SQLite.
Just run it:  python scripts/db_check.py

It auto-detects DATABASE_URL from .env and tells you exactly what's wrong
and how to fix it.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db_manager import test_connection, get_db_info

info = get_db_info()
result = test_connection()

print("="*60)
print("  Digital Campus — Database Connection Check")
print("="*60)
print(f"  Type      : {result['type']}")
print(f"  URL       : {result['url_masked']}")
if result.get('has_local_replica'):
    print(f"  Local REPL: {result['local_replica']}")
print("-"*60)

if result["ok"]:
    print(f"  ✅ CONNECTED  ({result['latency_ms']} ms, {result['tables']} tables)")
    if result["type"] == "PostgreSQL":
        print(f"  pgvector  : {'✅ enabled' if result.get('pgvector') else '⚠️  not installed (run: CREATE EXTENSION vector)'}")
    if result["type"] == "SQLite":
        print(f"  File      : {result['url_masked'].split(':///')[-1]}")
    print(f"  Tables    : {', '.join(result['table_list'][:10])}{' ...' if len(result['table_list'])>10 else ''}")
    print()
    print("  ✅ Ready — you can start the server:")
    print("     .venv/bin/uvicorn app.main:app --reload --port 8000")
else:
    print(f"  ❌ FAILED: {result['error']}")
    print()
    if result["type"] == "PostgreSQL":
        print("  FIX for PostgreSQL:")
        print("  1. Is Postgres running?  docker-compose up -d db   OR   pg_ctl status")
        print("  2. Check .env:  DATABASE_URL=postgresql+psycopg2://dc_user:dc_pass@localhost:5432/digital_campus")
        print("  3. Create DB/user if needed:")
        print("     CREATE USER dc_user WITH PASSWORD 'dc_pass';")
        print("     CREATE DATABASE digital_campus OWNER dc_user;")
        print("     GRANT ALL PRIVILEGES ON DATABASE digital_campus TO dc_user;")
        print("  4. Then run:  python scripts/init_db.py")
    else:
        print("  FIX for SQLite:")
        print("  1. Check .env:  DATABASE_URL=sqlite:///./digital_campus.db")
        print("  2. Ensure folder is writable, then run:")
        print("     python scripts/init_db.py")
    sys.exit(1)
print("="*60)
