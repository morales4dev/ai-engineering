"""Create estimations table (was SQLAlchemy create_all).

Revision ID: 0000_estimations
Revises:
Create Date: 2026-10-15 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0000_estimations"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "estimations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("project_type", sa.String, nullable=False),
        sa.Column("detail_level", sa.String, nullable=False),
        sa.Column("output_format", sa.String, nullable=False),
        sa.Column("response_payload", JSONB, nullable=False),
        sa.Column("prompt_version", sa.String, nullable=True),
        sa.Column(
            "cached",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
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


def downgrade() -> None:
    op.drop_table("estimations")
