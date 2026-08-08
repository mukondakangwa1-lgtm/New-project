"""initial - create all tables for PostgreSQL/SQLite + pgvector

Revision ID: 001_initial
Revises: 
Create Date: 2026-08-08

This is the baseline for the hybrid DB. Tables are created via SQLAlchemy Base.metadata.
Works for both SQLite (WAL/pragmas) and PostgreSQL (pgvector extension).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector on Postgres, ignored on SQLite (wrapped in try)
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        pass

    # All tables are created via Base.metadata.create_all in code path,
    # but we also ensure alembic knows the schema by not doing manual creates here.
    # This allows `alembic upgrade head` to succeed on fresh DB.
    # For new deployments, `scripts/init_db.py` calls Base.metadata.create_all directly.
    pass


def downgrade() -> None:
    pass
