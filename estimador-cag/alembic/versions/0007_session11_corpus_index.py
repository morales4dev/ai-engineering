"""Persist corpus expansion runs and provision the halfvec HNSW index."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0007_session11_corpus_index"
down_revision = "0006_session10_wizard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corpus_index_runs",
        sa.Column("job_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("chunk_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("processed", sa.Integer, nullable=False),
        sa.Column("indexed", sa.Integer, nullable=False),
        sa.Column("skipped", sa.Integer, nullable=False),
        sa.Column("chunks_created", sa.Integer, nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("before_stats", JSONB, nullable=False),
        sa.Column("after_stats", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS chunks_embedding_halfvec_idx ON chunks "
        "USING hnsw ((embedding::halfvec(1536)) halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )


def downgrade() -> None:
    # The index may predate this migration (the Session 8 lab creates it).
    op.drop_table("corpus_index_runs")
