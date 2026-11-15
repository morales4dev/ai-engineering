"""Async data-access layer for the vector store.

The store never opens or commits sessions: the caller (ingest service,
retriever) owns the ``AsyncSession`` so a whole ingest — duplicate check,
document row, chunk rows — fits in ONE transaction. A failure anywhere rolls
everything back and leaves no orphan ``documents`` row.
"""

from __future__ import annotations

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Integer, Row, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from generation.rag.chunk_types import BUDGET_COMPONENT
from generation.rag.schemas import EmbeddedChunk
from generation.rag.store.models import ChunkRow, DocumentRow, EMBEDDING_DIMENSIONS


class ChunkStore:
    """CRUD + similarity search over ``documents``/``chunks``."""

    async def find_document_id(self, session: AsyncSession, source_path: str) -> int | None:
        """Return the id of the document already ingested from ``source_path``,
        or ``None``. Backs the application-level 409 duplicate guard."""
        stmt = select(DocumentRow.id).where(DocumentRow.source_path == source_path)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def persist_document_with_chunks(
        self,
        session: AsyncSession,
        *,
        source_path: str,
        document_type: str,
        doc_metadata: dict,
        embedded_chunks: list[EmbeddedChunk],
        chunk_type: str = BUDGET_COMPONENT,
    ) -> int:
        """Insert the document row plus all its chunk rows. No commit here —
        the caller's transaction decides when (and whether) anything lands.

        ``chunk_type`` is stamped on every chunk (filterable column); it
        defaults to ``budget_component`` so existing callers are unaffected."""
        document = DocumentRow(
            source_path=source_path,
            document_type=document_type,
            metadata_=doc_metadata,
        )
        session.add(document)
        await session.flush()  # assigns document.id without committing

        session.add_all(
            ChunkRow(
                document_id=document.id,
                chunk_type=chunk_type,
                content=chunk.text,
                embedding=chunk.embedding,
                metadata_=chunk.metadata,
            )
            for chunk in embedded_chunks
        )
        return document.id

    async def search(
        self, session: AsyncSession, *, query_vector: list[float], k: int
    ) -> list[Row]:
        """k nearest chunks by cosine distance (``<=>``) over the halfvec cast.

        Orders by ``embedding::halfvec(1536)`` so Postgres can use
        ``chunks_embedding_halfvec_idx`` when that index exists. Without it:
        seq scan plus the cast. HTTP contract unchanged.

        Cosine over L2/inner product: OpenAI embeddings are normalized so the
        ranking would be equivalent, but cosine keeps us aligned with the RAG
        literature and with the ``vector_cosine_ops`` / ``halfvec_cosine_ops``
        operator classes of the HNSW indexes — operator/index mismatch makes
        Postgres silently ignore the index.
        """
        # distance = ChunkRow.embedding.cosine_distance(query_vector)
        distance = cast(ChunkRow.embedding, HALFVEC(EMBEDDING_DIMENSIONS)).cosine_distance(query_vector)
        stmt = (
            select(
                ChunkRow.id,
                ChunkRow.document_id,
                ChunkRow.chunk_type,
                ChunkRow.content,
                ChunkRow.metadata_,
                distance.label("distance"),
            )
            .order_by(distance)
            .limit(k)
        )
        return list((await session.execute(stmt)).all())

    async def search_filtered(
        self,
        session: AsyncSession,
        *,
        query_vector: list[float],
        top_k: int = 10,
        distance_threshold: float = 0.6,
        sectors: list[str] | None = None,
        project_year_min: int | None = None,
        project_year_max: int | None = None,
        chunk_types: list[str] | None = None,
        document_types: list[str] | None = None,
        extra_filters: list | None = None,
    ) -> tuple[list[Row], int]:
        """k-NN search with structural pre-filtering and a relevance threshold.

        Session 9 retrieval. Structural filters (sector / project year / chunk
        type) narrow the candidate space BEFORE the vector ranking — the metadata
        is persisted in JSONB (``client_sector``, ``year``) and the ``chunk_type``
        column. Each filter follows the ``(:filter IS NULL OR …)`` pattern: a
        ``None`` filter simply does not apply. The distance threshold then drops
        chunks that are not actually close (no "confidently retrieving garbage").

        Returns
        -------
        tuple[list[Row], int]
            ``(rows, candidates_evaluated)`` where ``rows`` are the top-k chunks
            under the threshold (ascending distance) and ``candidates_evaluated``
            is how many chunks matched the structural filters before the
            threshold/limit were applied.
        """
        structural_filters = self._structural_filters(
            sectors=sectors,
            project_year_min=project_year_min,
            project_year_max=project_year_max,
            chunk_types=chunk_types,
        )
        if document_types:
            structural_filters.append(DocumentRow.document_type.in_(document_types))
        structural_filters.extend(extra_filters or [])

        distance = cast(ChunkRow.embedding, HALFVEC(EMBEDDING_DIMENSIONS)).cosine_distance(
            query_vector
        )

        count_stmt = select(func.count()).select_from(ChunkRow)
        if document_types:
            count_stmt = count_stmt.join(
                DocumentRow, ChunkRow.document_id == DocumentRow.id
            )
        count_stmt = count_stmt.where(*structural_filters)
        candidates_evaluated = int((await session.execute(count_stmt)).scalar_one())

        stmt = select(
            ChunkRow.id,
            ChunkRow.document_id,
            ChunkRow.chunk_type,
            ChunkRow.content,
            ChunkRow.metadata_,
            distance.label("distance"),
        )
        if document_types:
            stmt = stmt.join(DocumentRow, ChunkRow.document_id == DocumentRow.id)
        stmt = (
            stmt.where(*structural_filters)
            .where(distance <= distance_threshold)
            .order_by(distance)
            .limit(top_k)
        )
        rows = list((await session.execute(stmt)).all())
        return rows, candidates_evaluated

    async def search_lexical(
        self,
        session: AsyncSession,
        *,
        query_text: str,
        top_k: int = 50,
        sectors: list[str] | None = None,
        project_year_min: int | None = None,
        project_year_max: int | None = None,
        chunk_types: list[str] | None = None,
        document_types: list[str] | None = None,
        extra_filters: list | None = None,
    ) -> list[Row]:
        """Return full-text matches, ranked by PostgreSQL cover density."""
        tsquery = func.plainto_tsquery("english", query_text)
        rank = func.ts_rank_cd(ChunkRow.content_tsv, tsquery)
        structural_filters = self._structural_filters(
            sectors=sectors,
            project_year_min=project_year_min,
            project_year_max=project_year_max,
            chunk_types=chunk_types,
        )
        if document_types:
            structural_filters.append(DocumentRow.document_type.in_(document_types))
        structural_filters.extend(extra_filters or [])
        stmt = select(
            ChunkRow.id,
            ChunkRow.document_id,
            ChunkRow.chunk_type,
            ChunkRow.content,
            ChunkRow.metadata_,
            rank.label("rank"),
        )
        if document_types:
            stmt = stmt.join(DocumentRow, ChunkRow.document_id == DocumentRow.id)
        stmt = (
            stmt.where(ChunkRow.content_tsv.op("@@")(tsquery))
            .where(*structural_filters)
            .order_by(rank.desc())
            .limit(top_k)
        )
        return list((await session.execute(stmt)).all())

    @staticmethod
    def _structural_filters(
        *,
        sectors: list[str] | None,
        project_year_min: int | None,
        project_year_max: int | None,
        chunk_types: list[str] | None,
    ) -> list:
        sector_col = ChunkRow.metadata_["client_sector"].astext
        year_col = cast(ChunkRow.metadata_["year"].astext, Integer)
        filters = []
        if sectors:
            filters.append(sector_col.in_(sectors))
        if project_year_min is not None:
            filters.append(year_col >= project_year_min)
        if project_year_max is not None:
            filters.append(year_col <= project_year_max)
        if chunk_types:
            filters.append(ChunkRow.chunk_type.in_(chunk_types))
        return filters
