"""
Alembic environment configuration.

Supports dual-DB: PostgreSQL (ANALYTICS_DATABASE_URL) or SQLite (local dev).
"""
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _get_database_url() -> str:
    """Resolve database URL from environment or fallback to SQLite."""
    pg_url = os.environ.get('ANALYTICS_DATABASE_URL')
    if pg_url:
        return pg_url
    # SQLite fallback — same path as auth_db.py
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    db_path = project_root / "data" / "auth" / "auth.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without DB connection)."""
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with DB connection)."""
    url = _get_database_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
