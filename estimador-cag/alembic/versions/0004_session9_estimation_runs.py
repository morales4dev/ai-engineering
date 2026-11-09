"""Session 9 live — estimation_runs (wizard ejecuciones).

Revision ID: 0004_session9_estimation_runs
Revises: 0003_session8_pgvector
Create Date: 2026-11-09 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004_session9_estimation_runs"
down_revision: Union[str, None] = "0003_session8_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "estimation_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("transcript", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="started",
        ),
        sa.Column(
            "current_step",
            sa.String(length=50),
            nullable=False,
            server_default="transcript",
        ),
        sa.Column(
            "reformulation",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "retrieval",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "augmentation",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "generation",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "adjusted_breakdown",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
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
        "idx_estimation_runs_created_at",
        "estimation_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_estimation_runs_created_at",
        table_name="estimation_runs",
    )
    op.drop_table("estimation_runs")
