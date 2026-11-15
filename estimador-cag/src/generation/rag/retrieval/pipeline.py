"""Hybrid retrieval with optional recall-then-cross-encoder reranking."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_async_session_factory, get_chunk_store
from generation.rag.errors import RetrievalError
from generation.rag.retrieval.collections import Collection, HardFilters, spec_for
from generation.rag.retrieval.fusion import reciprocal_rank_fusion
from generation.rag.schemas import RetrievalResult, RetrievedChunk

log = structlog.get_logger()


def _row_to_chunk(row, *, distance: float | None) -> RetrievedChunk:
    metadata = row.metadata_ or {}
    return RetrievedChunk(
        id=row.id,
        content=row.content,
        sector=str(metadata.get("client_sector", "unknown")),
        project_year=int(metadata.get("year", 0)),
        chunk_type=row.chunk_type,
        distance=distance if distance is not None else 1.0,
        has_vector_distance=distance is not None,
        budget_id=metadata.get("budget_id"),
        estimated_hours=metadata.get("estimated_hours"),
    )


@dataclass
class CollectionHits:
    """Vector/lexical recall for one collection and one transformed query."""

    collection: Collection
    candidates: dict[int, RetrievedChunk]
    vector_ids: list[int]
    lexical_ids: list[int]
    candidates_evaluated: int

    def fused_order(self, *, search_mode: str, rrf_k: int) -> list[RetrievedChunk]:
        if search_mode == "hybrid":
            fused = reciprocal_rank_fusion([self.vector_ids, self.lexical_ids], k=rrf_k)
            return [self.candidates[chunk_id] for chunk_id, _score in fused]
        return [self.candidates[chunk_id] for chunk_id in self.vector_ids]


async def hybrid_search_one(
    session: AsyncSession,
    store,
    *,
    collection: Collection,
    query_embedding: list[float],
    query_text: str,
    search_mode: str,
    recall_k: int,
    top_k: int,
    distance_threshold: float,
    will_rerank: bool,
    hard_filters: HardFilters,
) -> CollectionHits:
    """Run the existing hybrid recall path restricted to one metadata collection."""
    spec = spec_for(collection)
    extra_filters = spec.hard_filter_clauses(hard_filters)
    wide = will_rerank or search_mode == "hybrid"
    vector_rows, candidates_evaluated = await store.search_filtered(
        session,
        query_vector=query_embedding,
        top_k=recall_k if wide else top_k,
        distance_threshold=distance_threshold,
        chunk_types=list(spec.chunk_types),
        document_types=list(spec.document_types),
        extra_filters=extra_filters,
    )
    lexical_rows = (
        await store.search_lexical(
            session,
            query_text=query_text,
            top_k=recall_k,
            chunk_types=list(spec.chunk_types),
            document_types=list(spec.document_types),
            extra_filters=extra_filters,
        )
        if search_mode == "hybrid"
        else []
    )
    candidates = {
        row.id: spec.to_chunk(row, distance=float(row.distance)) for row in vector_rows
    }
    for row in lexical_rows:
        candidates.setdefault(row.id, spec.to_chunk(row, distance=None))
    return CollectionHits(
        collection=collection,
        candidates=candidates,
        vector_ids=[row.id for row in vector_rows],
        lexical_ids=[row.id for row in lexical_rows],
        candidates_evaluated=candidates_evaluated,
    )


async def retrieve(
    *,
    query_embedding: list[float],
    query_text: str,
    search_mode: str,
    rerank: bool,
    top_k: int,
    recall_k: int,
    rerank_top_n: int,
    distance_threshold: float,
    rrf_k: int,
    sectors: list[str] | None = None,
    project_year_min: int | None = None,
    project_year_max: int | None = None,
    chunk_types: list[str] | None = None,
    reranker=None,
) -> RetrievalResult:
    """Retrieve a wide candidate pool, optionally fuse and rerank it."""
    store = get_chunk_store()
    started = time.perf_counter()
    wide = rerank or search_mode == "hybrid"
    vector_limit = recall_k if wide else top_k

    try:
        async with get_async_session_factory()() as session:
            vector_rows, candidates_evaluated = await store.search_filtered(
                session,
                query_vector=query_embedding,
                top_k=vector_limit,
                distance_threshold=distance_threshold,
                sectors=sectors,
                project_year_min=project_year_min,
                project_year_max=project_year_max,
                chunk_types=chunk_types,
            )
            lexical_rows = (
                await store.search_lexical(
                    session,
                    query_text=query_text,
                    top_k=recall_k,
                    sectors=sectors,
                    project_year_min=project_year_min,
                    project_year_max=project_year_max,
                    chunk_types=chunk_types,
                )
                if search_mode == "hybrid"
                else []
            )
    except Exception as exc:  # database failures become retrieval errors.
        log.error("rag_hybrid_search_failed", error_type=type(exc).__name__, error=str(exc)[:200])
        raise RetrievalError("Vector store query failed.") from exc

    candidates: dict[int, RetrievedChunk] = {
        row.id: _row_to_chunk(row, distance=float(row.distance)) for row in vector_rows
    }
    for row in lexical_rows:
        candidates.setdefault(row.id, _row_to_chunk(row, distance=None))

    if search_mode == "hybrid":
        fused = reciprocal_rank_fusion(
            [[row.id for row in vector_rows], [row.id for row in lexical_rows]],
            k=rrf_k,
        )
        ordered = [candidates[chunk_id] for chunk_id, _score in fused]
    else:
        ordered = [candidates[row.id] for row in vector_rows]

    if rerank and ordered:
        try:
            if reranker is None:
                from dependencies import get_reranker

                reranker = get_reranker()
            final = await asyncio.to_thread(
                reranker.rerank, query_text, ordered[:recall_k], top_n=rerank_top_n
            )
        except Exception as exc:  # model load/scoring failure.
            log.error("rag_reranking_failed", error_type=type(exc).__name__, error=str(exc)[:200])
            raise RetrievalError("Cross-encoder reranking failed.") from exc
    else:
        final = ordered[:top_k]

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "rag_retrieve_done",
        search_mode=search_mode,
        rerank=rerank,
        vector_hits=len(vector_rows),
        lexical_hits=len(lexical_rows),
        results=len(final),
        candidates_evaluated=candidates_evaluated,
        search_time_ms=elapsed_ms,
    )
    return RetrievalResult(
        chunks=final,
        low_confidence=not final,
        candidates_evaluated=candidates_evaluated,
    )
