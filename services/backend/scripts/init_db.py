#!/usr/bin/env python3
"""
One-command DB initializer — Works for BOTH PostgreSQL and SQLite.
Usage:
    python scripts/init_db.py                 # uses DATABASE_URL from .env
    python scripts/init_db.py --seed          # also create superadmin
    python scripts/init_db.py --reset         # drop + recreate (DANGEROUS)

After you create a PostgreSQL account/DB, just run this and it connects.
After you download SQLite, just run this and it creates the .db file.
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.config import settings
from app.core.db_manager import init_all, test_connection, get_db_info
from app.core.database import engine, Base

def main():
    ap = argparse.ArgumentParser(description="Init DB — Postgres or SQLite")
    ap.add_argument("--seed", action="store_true", help="create superadmin (admin@campus.edu / superadmin123)")
    ap.add_argument("--reset", action="store_true", help="DROP all tables first")
    ap.add_argument("--no-pgvector", action="store_true", help="skip CREATE EXTENSION vector")
    args = ap.parse_args()

    info = get_db_info()
    print(f"\n→ Database: {info['type']} — {info['url_masked']}")

    if args.reset:
        print("⚠️  --reset: dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("   Dropped.")

    # For SQLite, ensure directory exists
    if settings.is_sqlite:
        # extract path from sqlite:///...
        url = settings.DATABASE_URL
        if ":///" in url:
            db_path = url.split(":///")[-1].split("?")[0]
            # handle relative path
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            print(f"→ SQLite file: {p.resolve()}")

    print("→ Creating tables...")
    result = init_all(with_pgvector=not args.no_pgvector)

    if not result.get("ok"):
        print(f"❌ Failed: {result.get('error')}")
        sys.exit(1)

    print(f"✅ Tables ready: {result['tables']} tables ({result['latency_ms']} ms)")
    if result.get("pgvector"):
        print("✅ pgvector enabled")
    elif settings.is_postgres:
        print(f"ℹ️  pgvector: {result.get('pgvector_attempt', 'not enabled')} — enable manually if needed: CREATE EXTENSION vector;")

    if args.seed:
        print("\n→ Seeding superadmin...")
        # Import seed logic inline to avoid re-running seed.py as subprocess
        from app.core.security import get_password_hash
        from app.models import User
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            admin_email = "admin@campus.edu"
            admin_password = "superadmin123"
            existing = db.query(User).filter(User.email == admin_email).first()
            if existing:
                existing.hashed_password = get_password_hash(admin_password)
                existing.is_admin = True
                existing.full_name = "Superadmin"
                db.commit()
                print(f"✅ Superadmin updated: {admin_email}")
            else:
                admin = User(email=admin_email, full_name="Superadmin", hashed_password=get_password_hash(admin_password), is_admin=True)
                db.add(admin)
                db.commit()
                print(f"✅ Superadmin created: {admin_email}")
            print(f"   Login: {admin_email} / {admin_password}")
        finally:
            db.close()

    print("\n✅ DONE — Run the server:")
    print("   .venv/bin/uvicorn app.main:app --reload --port 8000")
    print("   Docs: http://localhost:8000/docs\n")

if __name__ == "__main__":
    main()
