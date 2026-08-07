"""
Alembic env.py minimal setup. Uses the settings.DATABASE_URL and app.core.database.Base metadata.
This file allows developers to run `alembic revision --autogenerate` from services/backend.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except (KeyError, ValueError):
        # The minimal checked-in alembic.ini does not define every logger
        # section expected by fileConfig; migrations should still run.
        pass

# Add project path and import every model module so Alembic can see the
# complete metadata during revision autogeneration.
from app.core.config import settings
from app.core.database import Base
from app import models as _models  # noqa: F401
from app import models_extended as _models_extended  # noqa: F401

# Set SQLAlchemy URL from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# target_metadata for 'autogenerate' support
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
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
