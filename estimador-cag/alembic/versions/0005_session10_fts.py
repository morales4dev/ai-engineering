"""Add generated full-text search vector to chunks.

Revision ID: 0005_session10_fts
Revises: 0004_session9_estimation_runs
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_session10_fts"
down_revision: str | None = "0004_session9_estimation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The RAG corpus and reformulated search queries are English.
    op.execute(
        "ALTER TABLE chunks ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.create_index(
        "ix_chunks_content_tsv",
        "chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_content_tsv", table_name="chunks")
    op.drop_column("chunks", "content_tsv")
