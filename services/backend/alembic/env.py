"""
Alembic env.py — Hybrid: works for BOTH SQLite and PostgreSQL.
- Uses settings.DATABASE_URL
- Skips pgvector extension on SQLite automatically
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

# Import all models so metadata is populated
try:
    import app.models  # noqa: F401, F403
    import app.models_extended  # noqa: F401
except Exception:
    pass

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Only ensure pgvector on Postgres; skip for SQLite (no extension support)
        if settings.is_postgres:
            try:
                connection.execute(connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector"))
                connection.commit()
            except Exception:
                pass
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
