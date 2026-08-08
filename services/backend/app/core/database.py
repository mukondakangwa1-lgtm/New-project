"""
Database connection with hybrid PostgreSQL + SQLite support.

- Single DATABASE_URL drives primary engine (SQLite on laptop, Postgres in prod).
- Automatically sets SQLite pragmas for performance (WAL, NORMAL, FK ON).
- Optional DATABASE_URL_LOCAL gives a second SQLite engine for offline replica / queue
  (see database_hybrid.py for dual-engine helpers).

Usage (simple - Pattern A):
    from app.core.database import engine, SessionLocal, Base, get_db, init_db

Usage (offline replica - Pattern B):
    from app.core.database import get_local_db  # + DATABASE_URL_LOCAL in .env
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

# ── Primary engine ──────────────────────────────────────────
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
    # Postgres pool tuning (SQLite ignores these)
    pool_pre_ping=True if settings.is_postgres else False,
)

# Optimize SQLite: WAL + NORMAL + large cache + FK enforcement
if settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA cache_size=-64000;")  # 64MB
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session per request (primary DB)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (dev convenience — use Alembic in production)."""
    # Import models here so metadata is populated even if caller didn't import them
    try:
        import app.models  # noqa: F401
        import app.models_extended  # noqa: F401
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)


# ── Optional local replica engine (Pattern B) ───────────────
LocalSessionLocal = None
local_engine = None

if settings.has_local_replica:
    _local_connect_args = {"check_same_thread": False}
    local_engine = create_engine(
        settings.DATABASE_URL_LOCAL,
        connect_args=_local_connect_args,
        echo=False,
    )

    @event.listens_for(local_engine, "connect")
    def _set_local_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA cache_size=-64000;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    LocalSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

    def get_local_db():
        """FastAPI dependency for local SQLite replica."""
        db = LocalSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def init_local_db():
        try:
            import app.models  # noqa: F401
            import app.models_extended  # noqa: F401
        except Exception:
            pass
        Base.metadata.create_all(bind=local_engine)
else:
    def get_local_db():  # type: ignore
        raise RuntimeError("DATABASE_URL_LOCAL not set — configure it in .env to use local replica")

    def init_local_db():  # type: ignore
        raise RuntimeError("DATABASE_URL_LOCAL not set")
