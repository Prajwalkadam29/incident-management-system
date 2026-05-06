"""
Alembic environment — configured for async SQLAlchemy (asyncpg).

Key design decisions:
- URL is sourced from app Settings (respects .env) — never hardcoded here.
- Uses asyncio.run() to drive async connection for online migrations.
- NullPool is used for migrations (no persistent connections needed).
- All app models are imported so autogenerate can detect schema drift.
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from typing import Optional

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Make sure the app package is importable ──────────────────────────
# When running `alembic upgrade head` from /app (inside Docker),
# the app/ directory is already on the path. But for local runs
# from the backend/ directory, we add the current dir explicitly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── App imports ───────────────────────────────────────────────────────
from app.core.config import settings  # noqa: E402

# Import ALL models so their tables are registered on Base.metadata.
# Without these imports, autogenerate won't detect the tables.
from app.db.postgres import Base  # noqa: E402
from app.models.sql_models import (  # noqa: E402, F401
    WorkItem,
    RCARecord,
    IncidentEvent,
)

# ── Alembic config ────────────────────────────────────────────────────
alembic_cfg = context.config

# Override the sqlalchemy.url from app settings — never from alembic.ini
alembic_cfg.set_main_option("sqlalchemy.url", settings.POSTGRES_URL)

# Set up Python logging from the alembic.ini [loggers] section
if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# Target metadata — Alembic compares this against the live DB for autogenerate
target_metadata = Base.metadata


# ── Offline mode (generates SQL without connecting to DB) ─────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generate SQL script without a live
    DB connection. Useful for generating migration SQL for DBA review.

    Usage: alembic upgrade head --sql > migration.sql
    """
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,        # detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (connects to DB and runs migrations) ──────────────────

def do_run_migrations(connection: Connection) -> None:
    """Synchronous migration runner — called via connection.run_sync()."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,         # detect column type changes (e.g., String → Integer)
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine, connect, and run migrations.
    NullPool ensures no connections are left open after migrations complete.
    """
    connectable = async_engine_from_config(
        alembic_cfg.get_section(alembic_cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
