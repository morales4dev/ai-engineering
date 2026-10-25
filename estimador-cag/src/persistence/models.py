"""SQLAlchemy ORM models.

One ``DeclarativeBase`` for Alembic. Four tables:

* ``estimations`` — successful one-shot ``/estimate`` rows (was ``create_all``).
* ``pseudonym_mappings`` — reversible PII mapping keyed by
  ``(entity_type, original_hash)``.
* ``ingestion_jobs`` — book-keeping for ``POST /ingestion/runs``.
* ``chunking_comparisons`` — successful ``POST /embeddings/compare`` rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Single declarative base — picked up by Alembic env.py."""


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


class PseudonymMappingRow(Base):
    __tablename__ = "pseudonym_mappings"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "original_hash", name="uq_mappings_entity_hash"
        ),
        Index("idx_mappings_lookup", "entity_type", "original_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    original_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    pseudonym: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestionJobRow(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (Index("idx_jobs_status", "status"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    documents_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ChunkingComparisonRow(Base):
    __tablename__ = "chunking_comparisons"
    __table_args__ = (Index("idx_chunking_comparisons_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    queries: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    corpus_label: Mapped[str] = mapped_column(
        String, nullable=False, default="budgets_sample"
    )
    corpus_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
