"""Lazy SQLAlchemy engine and per-request session.

Importing this module does not call ``create_engine``. ``get_session`` is a
FastAPI ``Depends`` and returns 503 when ``DATABASE_URL`` is unset.
"""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
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
