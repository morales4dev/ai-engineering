"""Lazy SQLAlchemy engines and per-request session helpers.

Importing this module does not call ``create_engine``. ``get_session`` is a
FastAPI ``Depends`` and returns 503 when ``DATABASE_URL`` is unset.

Two stacks coexist on purpose:

* **Sync (psycopg)** — ingestion jobs and compare history. ``get_engine`` / ``get_session``.
* **Async (asyncpg)** — RAG ingest / search.

Both read the same ``Settings.DATABASE_URL``. The async stack swaps the
driver token in code so compose stays on ``postgresql+psycopg://``.
"""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from config import get_settings


@lru_cache
def get_engine() -> Engine | None:
    """Build the engine on first use. ``None`` if ``DATABASE_URL`` is unset."""
    url = get_settings().DATABASE_URL
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a Session and closes it on exit."""
    engine = get_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="database is unavailable")
    session = Session(engine, autoflush=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()


def _async_database_url() -> str:
    """Derive the asyncpg URL from ``Settings.DATABASE_URL``.

    The canonical URL uses the sync driver (``postgresql+psycopg://``) because
    Alembic and the sync repositories run synchronously. The RAG store
    swaps the driver token instead of introducing a second env var.
    """
    url = get_settings().DATABASE_URL or ""
    if "+psycopg" in url:
        return url.replace("+psycopg", "+asyncpg")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@lru_cache
def get_async_engine() -> AsyncEngine | None:
    """Build the async engine on first use. ``None`` if ``DATABASE_URL`` is unset."""
    url = get_settings().DATABASE_URL
    if not url:
        return None
    return create_async_engine(_async_database_url(), pool_pre_ping=True)


@lru_cache
def get_async_session_factory() -> async_sessionmaker | None:
    """Session factory for the async stack. ``None`` if ``DATABASE_URL`` is unset.

    ``expire_on_commit=False`` so ORM objects (e.g. the freshly persisted
    document id) stay readable after the transaction commits.
    """
    engine = get_async_engine()
    if engine is None:
        return None
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
