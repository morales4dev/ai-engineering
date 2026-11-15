"""Add structure and per-task hours to estimation runs.

Revision ID: 0006_session10_wizard
Revises: 0005_session10_fts
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0006_session10_wizard"
down_revision = "0005_session10_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "estimation_runs",
        sa.Column("workflow_version", sa.String(16), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "estimation_runs",
        sa.Column("structure", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "estimation_runs",
        sa.Column("task_hours", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("estimation_runs", "task_hours")
    op.drop_column("estimation_runs", "structure")
    op.drop_column("estimation_runs", "workflow_version")
