"""Alembic migration environment.

The DB URL is read from ``config.Settings`` (not from alembic.ini). Host runs
``PYTHONPATH=src:. uv run alembic`` from ``estimador-cag/``; Compose already
has ``PYTHONPATH=/app``. Missing ``DATABASE_URL`` raises — do not pass None
to ``set_main_option``.
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
# Host layout: estimador-cag/src/. Container: src contents already live at /app.
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

from config import get_settings  # noqa: E402
from persistence.models import (  # noqa: E402, F401
    Base,
    ChunkingComparisonRow,
    EstimationRow,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_url = get_settings().DATABASE_URL
if not _url:
    raise RuntimeError("DATABASE_URL is not set; cannot run migrations")
config.set_main_option("sqlalchemy.url", _url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without a live connection — used by ``alembic upgrade --sql``."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
