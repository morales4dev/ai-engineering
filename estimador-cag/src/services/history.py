"""PostgreSQL persistence for successful /estimate responses.

FastAPI is the only process that talks to the DB. Streamlit only consumes HTTP.
Missing DATABASE_URL or a write error must not break /estimate (fail-open).
List/show raise HistoryUnavailable so the router can return 503.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

import structlog
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, desc, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from config import get_settings
from schemas.estimation import (
    EstimationDetail,
    EstimationListItem,
    EstimationRequest,
    EstimationResponse,
    EstimationResult,
)

log = structlog.get_logger()

_PREVIEW_CHARS = 80


class HistoryUnavailable(Exception):
    """Raised when list/show cannot reach Postgres."""


class Base(DeclarativeBase):
    pass


class EstimationRow(Base):
    __tablename__ = "estimations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    project_type: Mapped[str] = mapped_column(String, nullable=False)
    detail_level: Mapped[str] = mapped_column(String, nullable=False)
    output_format: Mapped[str] = mapped_column(String, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


@lru_cache
def get_engine() -> Engine | None:
    url = get_settings().DATABASE_URL
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


def init_db() -> None:
    """Create tables if DATABASE_URL is set. Must not crash boot."""
    engine = get_engine()
    if engine is None:
        log.warning("history_disabled", reason="no_database_url")
        return
    try:
        Base.metadata.create_all(engine)
        log.info("history_schema_ready")
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "history_schema_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )


def persist_estimation(request: EstimationRequest, response: EstimationResponse) -> None:
    """INSERT after a successful /estimate, including cached=true. Fail-open."""
    engine = get_engine()
    if engine is None:
        return
    try:
        Base.metadata.create_all(engine)
        row = EstimationRow(
            description=request.description,
            project_type=request.project_type.value,
            detail_level=request.detail_level.value,
            output_format=request.output_format.value,
            response_payload=response.model_dump(mode="json"),
            prompt_version=response.prompt_version,
            cached=response.cached,
        )
        with Session(engine) as session:
            session.add(row)
            session.commit()
        log.info("estimation_persisted", cached=response.cached)
    except Exception as exc:  # noqa: BLE001 — /estimate must still return
        log.warning(
            "estimation_persist_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )


def _preview(description: str) -> str:
    return description[:_PREVIEW_CHARS]


def _created_at(row: EstimationRow) -> datetime:
    value = row.created_at
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def list_estimations(limit: int = 20) -> list[EstimationListItem]:
    engine = get_engine()
    if engine is None:
        raise HistoryUnavailable("DATABASE_URL is not set")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            rows = session.scalars(
                select(EstimationRow).order_by(desc(EstimationRow.created_at)).limit(limit)
            ).all()
        return [
            EstimationListItem(
                id=row.id,
                description_preview=_preview(row.description),
                project_type=row.project_type,
                detail_level=row.detail_level,
                output_format=row.output_format,
                prompt_version=row.prompt_version,
                cached=row.cached,
                created_at=_created_at(row),
            )
            for row in rows
        ]
    except HistoryUnavailable:
        raise
    except Exception as exc:
        raise HistoryUnavailable(str(exc)[:200]) from exc


def get_estimation(estimation_id: int) -> EstimationDetail | None:
    engine = get_engine()
    if engine is None:
        raise HistoryUnavailable("DATABASE_URL is not set")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            row = session.get(EstimationRow, estimation_id)
            if row is None:
                return None
            payload = row.response_payload or {}
            result = EstimationResult.model_validate(payload.get("result", payload))
            return EstimationDetail(
                id=row.id,
                description_preview=_preview(row.description),
                project_type=row.project_type,
                detail_level=row.detail_level,
                output_format=row.output_format,
                prompt_version=row.prompt_version,
                cached=row.cached,
                created_at=_created_at(row),
                description=row.description,
                result=result,
            )
    except HistoryUnavailable:
        raise
    except Exception as exc:
        raise HistoryUnavailable(str(exc)[:200]) from exc
