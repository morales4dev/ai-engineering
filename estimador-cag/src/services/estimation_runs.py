"""PostgreSQL persistence for wizard ejecuciones (``estimation_runs``).

FastAPI is the only process that talks to the DB. Streamlit only consumes HTTP.
Unlike Chunking Lab history this store does **not** fail-open: losing a paid
generate is not acceptable. List/get/insert/update raise
``EstimationRunsUnavailable`` when Postgres is down (router maps 503).

Talks to Postgres only. Does not call the LLM or the retriever.
Schema is Alembic's job — this module does not create_all.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from generation.rag.wizard import WizardRun
from persistence.database import get_engine
from persistence.models import EstimationRunRow

log = structlog.get_logger()

_JSON_FIELDS = (
    "reformulation",
    "retrieval",
    "augmentation",
    "generation",
    "structure",
    "task_hours",
    "adjusted_breakdown",
)
_SCALAR_FIELDS = ("status", "current_step", "idempotency_key", "duration_ms", "transcript")


class EstimationRunsUnavailable(Exception):
    """Raised when Postgres cannot be reached."""


class RunNotFound(Exception):
    """Raised when an update/clear targets a missing ejecución."""

    def __init__(self, run_id: int) -> None:
        super().__init__(f"estimation run {run_id} not found")
        self.run_id = run_id


def _created_at(row: EstimationRunRow) -> datetime:
    value = row.created_at
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _updated_at(row: EstimationRunRow) -> datetime:
    value = row.updated_at
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_run(row: EstimationRunRow) -> WizardRun:
    return WizardRun(
        id=row.id,
        transcript=row.transcript,
        status=row.status,
        current_step=row.current_step,
        workflow_version=row.workflow_version,
        reformulation=dict(row.reformulation or {}),
        retrieval=dict(row.retrieval or {}),
        augmentation=dict(row.augmentation or {}),
        generation=dict(row.generation or {}),
        structure=dict(row.structure or {}),
        task_hours=dict(row.task_hours or {}),
        adjusted_breakdown=dict(row.adjusted_breakdown or {}),
        idempotency_key=row.idempotency_key,
        duration_ms=row.duration_ms,
        created_at=_created_at(row),
        updated_at=_updated_at(row),
    )


def _require_engine():
    engine = get_engine()
    if engine is None:
        raise EstimationRunsUnavailable("DATABASE_URL is not set")
    return engine


def insert(*, transcript: str, idempotency_key: str | None = None) -> WizardRun:
    """INSERT a new ejecución. Raises if Postgres is down."""
    engine = _require_engine()
    try:
        row = EstimationRunRow(
            transcript=transcript,
            idempotency_key=idempotency_key,
            workflow_version="s10",
        )
        with Session(engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            run = _to_run(row)
        log.info("estimation_run_inserted", run_id=run.id)
        return run
    except EstimationRunsUnavailable:
        raise
    except Exception as exc:
        raise EstimationRunsUnavailable(str(exc)[:200]) from exc


def get(run_id: int) -> WizardRun | None:
    engine = _require_engine()
    try:
        with Session(engine) as session:
            row = session.get(EstimationRunRow, run_id)
            if row is None:
                return None
            return _to_run(row)
    except EstimationRunsUnavailable:
        raise
    except Exception as exc:
        raise EstimationRunsUnavailable(str(exc)[:200]) from exc


def list_runs(limit: int = 20) -> list[WizardRun]:
    engine = _require_engine()
    try:
        with Session(engine) as session:
            rows = session.scalars(
                select(EstimationRunRow)
                .where(EstimationRunRow.workflow_version == "s10")
                .order_by(desc(EstimationRunRow.created_at))
                .limit(limit)
            ).all()
        return [_to_run(row) for row in rows]
    except EstimationRunsUnavailable:
        raise
    except Exception as exc:
        raise EstimationRunsUnavailable(str(exc)[:200]) from exc


def update(run_id: int, **fields) -> WizardRun:
    """Patch JSON / scalar columns. Raises if missing or Postgres is down."""
    unknown = set(fields) - set(_JSON_FIELDS) - set(_SCALAR_FIELDS)
    if unknown:
        raise TypeError(f"unknown estimation_runs fields: {sorted(unknown)}")
    engine = _require_engine()
    try:
        with Session(engine) as session:
            row = session.get(EstimationRunRow, run_id)
            if row is None:
                raise RunNotFound(run_id)
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return _to_run(row)
    except (EstimationRunsUnavailable, RunNotFound):
        raise
    except Exception as exc:
        raise EstimationRunsUnavailable(str(exc)[:200]) from exc
