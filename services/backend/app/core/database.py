"""
Database connection with multi-db support (SQLite for dev, Postgres for prod).
Adjusted connect_args depending on the URL so engine works with Postgres (no check_same_thread) and with SQLite.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

# Choose connect args based on DB type
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
)

if settings.DATABASE_URL.startswith("sqlite"):
    # Production-grade SQLite pragmas: WAL for concurrent readers, busy
    # timeout so writers queue instead of erroring, FK enforcement on.
    @event.listens_for(engine, "connect")
    def _tune_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (dev convenience — use Alembic in production)."""
    Base.metadata.create_all(bind=engine)
