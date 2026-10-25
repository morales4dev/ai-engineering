"""Session 7 live — chunking_comparisons (compare history).

Revision ID: 0002_chunking_comparisons
Revises: 0001_session6_initial
Create Date: 2026-10-25 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002_chunking_comparisons"
down_revision: Union[str, None] = "0001_session6_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunking_comparisons",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategies", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("queries", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("top_k", sa.Integer, nullable=False, server_default="3"),
        sa.Column(
            "corpus_label",
            sa.String,
            nullable=False,
            server_default="budgets_sample",
        ),
        sa.Column("corpus_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "response_payload",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_chunking_comparisons_created_at",
        "chunking_comparisons",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_chunking_comparisons_created_at",
        table_name="chunking_comparisons",
    )
    op.drop_table("chunking_comparisons")
