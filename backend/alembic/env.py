"""Alembic environment: tells Alembic which database to use and which tables exist."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

import app.models  # noqa: F401  (registers all tables)
from app.config import get_settings
from app.db import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata
SCHEMAS = ("sap", "ar")


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in SCHEMAS
    return True


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, include_schemas=True, include_name=include_name)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        for s in SCHEMAS:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {s}"))
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata,
                          include_schemas=True, include_name=include_name,
                          version_table_schema="public", compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
