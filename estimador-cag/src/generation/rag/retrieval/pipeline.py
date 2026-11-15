"""Hybrid retrieval with optional recall-then-cross-encoder reranking."""

from __future__ import annotations

import asyncio
import time

import structlog

from dependencies import get_async_session_factory, get_chunk_store
from generation.rag.errors import RetrievalError
from generation.rag.retrieval.fusion import reciprocal_rank_fusion
from generation.rag.schemas import RetrievalResult, RetrievedChunk

log = structlog.get_logger()
_NO_VECTOR_DISTANCE = 1.0


def _row_to_chunk(row, *, distance: float) -> RetrievedChunk:
    return RetrievedChunk(
        id=row.id,
        content=row.content,
        sector=str(row.metadata_.get("client_sector", "unknown")),
        project_year=int(row.metadata_.get("year", 0)),
        chunk_type=row.chunk_type,
        distance=distance,
        budget_id=row.metadata_.get("budget_id"),
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
        candidates.setdefault(row.id, _row_to_chunk(row, distance=_NO_VECTOR_DISTANCE))

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
