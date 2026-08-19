"""
Alembic migration environment.

Reads the database URL and the application schema name from
``config.settings`` — the same single source of truth used by the
application, the seed and the repository layer. A hard-coded URL or schema
here would allow migrations and the running app to disagree about where
schema lives.

Fresh-database bootstrap:
    The configured application schema may not exist yet on a brand-new
    PostgreSQL server (for example ``alembic upgrade head`` against an empty
    container). Alembic records its version inside the application schema
    (``version_table_schema``), so the schema must exist before migrations
    run. It is created here with ``CREATE SCHEMA IF NOT EXISTS``.

    The schema name is validated by ``config.settings._validate_identifier``
    (plain ``[A-Za-z_][A-Za-z0-9_]*``), so interpolating it into DDL is safe
    and matches how the repository already interpolates it.

No ORM autogenerate:
    The project uses raw SQL / ``op.*`` migrations and no SQLAlchemy mapped
    classes, so ``target_metadata`` stays ``None`` and no schema-filtering
    callbacks (``include_name``) are configured.
"""
from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import create_engine, text

from alembic import context

from config.settings import database, monitoring

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

SCHEMA = monitoring.schema


def _run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a connection)."""
    context.configure(
        url=database.sqlalchemy_url,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=SCHEMA,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against a live connection)."""
    engine = create_engine(database.sqlalchemy_url, pool_pre_ping=True, future=True)
    with engine.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.commit()
        _run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
