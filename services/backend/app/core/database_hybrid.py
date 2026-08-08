"""
Hybrid helper — use when you want to explicitly control which engine handles which domain.

This module is OPTIONAL. For 95% of endpoints, just use `app.core.database.get_db`.
Only import from here if you implement Pattern C (domain split):

    from app.core.database_hybrid import primary_engine, local_engine, PrimarySession, LocalSession

Tables recommended for local_engine:
    - guardian_logs / shield logs
    - device_fingerprints
    - performance_logs
    - offline outbox (chat_messages.is_offline)

Everything else → primary_engine (Postgres in prod, SQLite in dev).

Example split usage in an endpoint:
    from sqlalchemy.orm import Session
    from app.core.database_hybrid import get_primary_db, get_local_db

    @router.post("/shield/log")
    def log_event(payload: dict, db: Session = Depends(get_local_db)):  # local SQLite
        ...

    @router.post("/courses")
    def create_course(payload: dict, db: Session = Depends(get_primary_db)):  # Postgres
        ...
"""
from app.core.database import (
    engine as primary_engine,
    SessionLocal as PrimarySession,
    get_db as get_primary_db,
    init_db as init_primary_db,
    local_engine,
    LocalSessionLocal as LocalSession,
    get_local_db,
    init_local_db,
    Base,
)

__all__ = [
    "primary_engine",
    "local_engine",
    "PrimarySession",
    "LocalSession",
    "get_primary_db",
    "get_local_db",
    "init_primary_db",
    "init_local_db",
    "Base",
]
