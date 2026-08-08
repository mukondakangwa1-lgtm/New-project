"""
Digital Campus - Unified DB Manager
Handles BOTH PostgreSQL and SQLite with zero code changes.
Just set DATABASE_URL and everything works.

Usage:
    from app.core.db_manager import test_connection, get_db_info, init_all

Supports:
  - SQLite (laptop):  sqlite:///./digital_campus.db  — zero setup, file-based
  - Postgres (prod):  postgresql+psycopg2://user:pass@host:5432/db — server
  - Auto-creates tables, enables pgvector, sets SQLite pragmas
"""
from __future__ import annotations
import os
import time
from typing import Dict, Any
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal, init_db


def get_db_info() -> Dict[str, Any]:
    """Return current DB type, URL (masked), and status."""
    url = settings.DATABASE_URL
    # mask password
    masked = url
    if "@" in url and "://" in url:
        try:
            prefix, rest = url.split("://", 1)
            if "@" in rest:
                creds, host = rest.rsplit("@", 1)
                if ":" in creds:
                    user, _ = creds.split(":", 1)
                    masked = f"{prefix}://{user}:****@{host}"
                else:
                    masked = f"{prefix}://****@{host}"
        except Exception:
            pass

    db_type = "PostgreSQL" if settings.is_postgres else "SQLite" if settings.is_sqlite else "Unknown"
    return {
        "type": db_type,
        "url_masked": masked,
        "is_sqlite": settings.is_sqlite,
        "is_postgres": settings.is_postgres,
        "has_local_replica": settings.has_local_replica,
        "local_replica": settings.DATABASE_URL_LOCAL if settings.has_local_replica else None,
    }


def test_connection(timeout: int = 5) -> Dict[str, Any]:
    """Test primary DB connection. Returns {ok: bool, latency_ms, tables, error}."""
    start = time.time()
    try:
        with engine.connect() as conn:
            # Simple query works on both SQLite and Postgres
            conn.execute(text("SELECT 1"))
            # Count tables
            insp = inspect(engine)
            tables = insp.get_table_names()
            latency = round((time.time() - start) * 1000, 1)

            # Check pgvector if postgres
            pgvector = False
            if settings.is_postgres:
                try:
                    r = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).fetchone()
                    pgvector = r is not None
                except Exception:
                    pass

            return {
                "ok": True,
                "latency_ms": latency,
                "tables": len(tables),
                "table_list": tables[:20],
                "pgvector": pgvector,
                "error": None,
                **get_db_info(),
            }
    except OperationalError as e:
        return {
            "ok": False,
            "latency_ms": None,
            "tables": 0,
            "table_list": [],
            "pgvector": False,
            "error": str(e).split("\n")[0][:300],
            **get_db_info(),
        }
    except Exception as e:
        return {
            "ok": False,
            "latency_ms": None,
            "tables": 0,
            "table_list": [],
            "pgvector": False,
            "error": str(e)[:300],
            **get_db_info(),
        }


def init_all(with_pgvector: bool = True) -> Dict[str, Any]:
    """Create all tables. For Postgres, also ensure pgvector extension."""
    info = get_db_info()
    try:
        # For Postgres, try to enable pgvector before creating tables
        if settings.is_postgres and with_pgvector:
            try:
                with engine.begin() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                info["pgvector_attempt"] = "ok"
            except Exception as e:
                info["pgvector_attempt"] = f"failed: {e}"

        # Create all tables
        init_db()
        # Verify
        result = test_connection()
        result["init"] = "ok"
        return result
    except Exception as e:
        info["init"] = f"failed: {e}"
        info["ok"] = False
        info["error"] = str(e)[:500]
        return info
