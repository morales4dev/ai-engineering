"""PostgreSQL persistence for successful /embeddings/compare responses.

FastAPI is the only process that talks to the DB. Streamlit only consumes HTTP.
Writes fail-open (same grain as persist_estimation). List/show raise
ComparisonHistoryUnavailable so the router can return 503.
Uses ``persistence.database.get_engine`` — not ``history.get_engine``.
Schema is Alembic's job — this module does not create_all.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from generation.rag.analysis.comparison import (
    CompareResponse,
    ComparisonDetail,
    ComparisonListItem,
)
from persistence.database import get_engine
from persistence.models import ChunkingComparisonRow

log = structlog.get_logger()


class ComparisonHistoryUnavailable(Exception):
    """Raised when list/show cannot reach Postgres."""


def _created_at(row: ChunkingComparisonRow) -> datetime:
    value = row.created_at
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def cost_total_usd(payload: dict) -> float:
    """Sum of per-strategy ``ingestion_cost_usd`` (Rails ``total_ingestion_cost_usd``)."""
    stats = payload.get("stats_per_strategy") or {}
    total = 0.0
    for item in stats.values():
        if isinstance(item, dict):
            total += float(item.get("ingestion_cost_usd") or 0.0)
        else:
            total += float(getattr(item, "ingestion_cost_usd", 0.0) or 0.0)
    return round(total, 6)


def _list_item(row: ChunkingComparisonRow) -> ComparisonListItem:
    payload = row.response_payload or {}
    return ComparisonListItem(
        id=row.id,
        created_at=_created_at(row),
        strategies=list(row.strategies or []),
        queries=list(row.queries or []),
        top_k=row.top_k,
        corpus_label=row.corpus_label,
        corpus_count=row.corpus_count,
        duration_ms=row.duration_ms,
        cost_total_usd=cost_total_usd(payload),
    )


def persist_comparison(
    *,
    strategies: list[str],
    queries: list[str],
    top_k: int,
    corpus_label: str,
    corpus_count: int,
    response: CompareResponse,
    duration_ms: int,
) -> None:
    """INSERT after a successful /embeddings/compare. Fail-open."""
    engine = get_engine()
    if engine is None:
        return
    try:
        row = ChunkingComparisonRow(
            strategies=strategies,
            queries=queries,
            top_k=top_k,
            corpus_label=corpus_label,
            corpus_count=corpus_count,
            response_payload=response.model_dump(mode="json"),
            duration_ms=duration_ms,
        )
        with Session(engine) as session:
            session.add(row)
            session.commit()
        log.info(
            "comparison_persisted",
            strategies=strategies,
            corpus_label=corpus_label,
            duration_ms=duration_ms,
        )
    except Exception as exc:  # noqa: BLE001 — /compare must still return
        log.warning(
            "comparison_persist_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )


def list_comparisons(limit: int = 20) -> list[ComparisonListItem]:
    engine = get_engine()
    if engine is None:
        raise ComparisonHistoryUnavailable("DATABASE_URL is not set")
    try:
        with Session(engine) as session:
            rows = session.scalars(
                select(ChunkingComparisonRow)
                .order_by(desc(ChunkingComparisonRow.created_at))
                .limit(limit)
            ).all()
        return [_list_item(row) for row in rows]
    except ComparisonHistoryUnavailable:
        raise
    except Exception as exc:
        raise ComparisonHistoryUnavailable(str(exc)[:200]) from exc


def get_comparison(comparison_id: int) -> ComparisonDetail | None:
    engine = get_engine()
    if engine is None:
        raise ComparisonHistoryUnavailable("DATABASE_URL is not set")
    try:
        with Session(engine) as session:
            row = session.get(ChunkingComparisonRow, comparison_id)
            if row is None:
                return None
            payload = row.response_payload or {}
            item = _list_item(row)
            return ComparisonDetail(
                **item.model_dump(),
                response=CompareResponse.model_validate(payload),
            )
    except ComparisonHistoryUnavailable:
        raise
    except Exception as exc:
        raise ComparisonHistoryUnavailable(str(exc)[:200]) from exc
