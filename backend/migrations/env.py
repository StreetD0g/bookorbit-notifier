"""Alembic environment for the notifier-owned SQLite schema."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.database.models  # noqa: F401  # Imports all mapped tables into Base.metadata.
from app.database.base import Base

config = context.config

# Operators can point Alembic at the same persistent data directory used by the
# application without editing a tracked configuration file.
database_url = os.getenv("BOOKORBIT_NOTIFIER_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL when an operator requests an offline migration plan."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations transactionally; batch mode keeps future SQLite alters safe."""

    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
