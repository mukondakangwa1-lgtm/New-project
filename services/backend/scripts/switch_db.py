#!/usr/bin/env python3
"""
Switch between SQLite and PostgreSQL with one command.
Usage:
    python scripts/switch_db.py sqlite          # → use .env.sqlite
    python scripts/switch_db.py postgres        # → use .env.postgres
    python scripts/switch_db.py sqlite --apply  # also copy to .env
    python scripts/switch_db.py status          # show current
"""
import sys, shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENV = ROOT / ".env"
SQLITE_ENV = ROOT / ".env.sqlite"
POSTGRES_ENV = ROOT / ".env.postgres"

def current_db():
    if not ENV.exists():
        return "none (.env missing)"
    txt = ENV.read_text()
    if "sqlite" in txt.lower():
        return "SQLite (sqlite://...)"
    if "postgresql" in txt.lower() or "postgres" in txt.lower():
        return "PostgreSQL (postgresql://...)"
    return "unknown"

def show_status():
    from app.core.db_manager import get_db_info
    sys.path.insert(0, str(ROOT))
    try:
        info = get_db_info()
        print(f"Current .env : {current_db()}")
        print(f"DATABASE_URL : {info['url_masked']}")
        print(f"Type         : {info['type']}")
    except Exception as e:
        print(f"Current .env : {current_db()}")
        print(f"Error reading config: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        show_status()
        sys.exit(0)
    cmd = sys.argv[1].lower()
    apply = "--apply" in sys.argv or "-a" in sys.argv

    if cmd == "status":
        show_status()
        sys.exit(0)

    if cmd in ("sqlite", "sqlite3", "lite"):
        src = SQLITE_ENV
        label = "SQLite"
    elif cmd in ("postgres", "postgresql", "pg", "psql"):
        src = POSTGRES_ENV
        label = "PostgreSQL"
    else:
        print(f"Unknown: {cmd}. Use: sqlite | postgres | status")
        sys.exit(1)

    if not src.exists():
        print(f"Template missing: {src}")
        sys.exit(1)

    print(f"→ Switching to {label}: {src} ")
    print(src.read_text())
    print("-"*60)
    if apply or input(f"Copy to .env and activate {label}? [Y/n]: ").strip().lower() in ("", "y", "yes"):
        shutil.copy(src, ENV)
        print(f"✅ .env now points to {label}")
        print("   Next: python scripts/init_db.py --seed")
        print("         python scripts/db_check.py")
    else:
        print(f"ℹ️  Preview only. Run with --apply to activate: python scripts/switch_db.py {cmd} --apply")
