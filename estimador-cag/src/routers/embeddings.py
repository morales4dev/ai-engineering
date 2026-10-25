"""HTTP layer for the embedding pipeline.

Thin router: it orchestrates chunker -> embedder -> response assembly and maps
failures to status codes. No business logic lives here.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException

from dependencies import ALL_STRATEGIES, build_chunkers, get_chunker, get_embedder
from generation.rag.chunking.structural import JSONStructuralChunker
from generation.rag.analysis.comparison import (
    ChunkingComparator,
    CompareRequest,
    CompareResponse,
    ComparisonDetail,
    ComparisonListResponse,
)
from generation.rag.embedding.embedder import OpenAIEmbedder, estimated_cost_usd
from generation.rag.schemas import IngestRequest, IngestResponse, IngestStats
from services.comparisons import (
    ComparisonHistoryUnavailable,
    get_comparison,
    list_comparisons,
    persist_comparison,
)

log = structlog.get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    chunker: JSONStructuralChunker = Depends(get_chunker),
    embedder: OpenAIEmbedder | None = Depends(get_embedder),
) -> IngestResponse:
    """Chunk the budgets, embed every chunk, and return vectors + stats."""
    if embedder is None:
        # No OPENAI_API_KEY configured. Generic message to the client, detail logged.
        log.error("embeddings_ingest_failed", reason="embedder_unavailable")
        raise HTTPException(status_code=500, detail="Embedding service is not available.")

    chunks = chunker.chunk(request.budgets)
    log.info(
        "embeddings_ingest_received",
        total_budgets=len(request.budgets),
        total_chunks=len(chunks),
    )

    try:
        embedded = embedder.embed_many(chunks)
    except Exception as exc:  # noqa: BLE001 — any embedding-API failure becomes a 500.
        log.error(
            "embeddings_ingest_failed",
            reason="embedding_api_error",
            error_type=type(exc).__name__,
            error=str(exc)[:300],
        )
        raise HTTPException(status_code=500, detail="Failed to generate embeddings.") from exc

    total_tokens = sum(chunk.token_count for chunk in embedded)
    stats = IngestStats(
        total_budgets=len(request.budgets),
        total_chunks=len(embedded),
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd(total_tokens),
    )
    log.info("embeddings_ingest_done", **stats.model_dump())
    return IngestResponse(chunks=embedded, stats=stats)


@router.post("/compare", response_model=CompareResponse)
def compare(
    request: CompareRequest,
    embedder: OpenAIEmbedder | None = Depends(get_embedder),
) -> CompareResponse:
    """Run several chunking strategies over the same budgets and compare them.

    Budgets come in the body. This handler does not read ``data/budgets_sample.json``.
    """
    if embedder is None:
        log.error("embeddings_compare_failed", reason="embedder_unavailable")
        raise HTTPException(status_code=500, detail="Embedding service is not available.")

    names = request.strategies or ALL_STRATEGIES
    try:
        chunkers = build_chunkers(names)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {exc.args[0]}") from exc
    except RuntimeError as exc:
        log.error("embeddings_compare_failed", reason="missing_api_key", error=str(exc))
        raise HTTPException(status_code=500, detail="Embedding service is not available.") from exc

    comparator = ChunkingComparator(chunkers, embedder)
    log.info(
        "embeddings_compare_received",
        total_budgets=len(request.budgets),
        strategies=names,
        n_queries=len(request.queries),
    )
    t0 = time.perf_counter()
    try:
        stats = comparator.compute_stats(request.budgets)
        queries = comparator.run_queries(request.budgets, request.queries, request.top_k)
    except Exception as exc:  # noqa: BLE001 — any chunker/embedding failure becomes a 500.
        log.error(
            "embeddings_compare_failed",
            reason="comparison_error",
            error_type=type(exc).__name__,
            error=str(exc)[:300],
        )
        raise HTTPException(status_code=500, detail="Failed to run chunking comparison.") from exc

    body = CompareResponse(stats_per_strategy=stats, queries_per_strategy=queries)
    persist_comparison(
        strategies=names,
        queries=request.queries,
        top_k=request.top_k,
        corpus_label=request.corpus_label or "budgets_sample",
        corpus_count=len(request.budgets),
        response=body,
        duration_ms=round((time.perf_counter() - t0) * 1000),
    )
    return body


@router.get("/comparisons", response_model=ComparisonListResponse)
def list_saved_comparisons() -> ComparisonListResponse:
    """Last 20 compares, newest first. No ``response_payload`` in the JSON."""
    try:
        return ComparisonListResponse(items=list_comparisons(limit=20))
    except ComparisonHistoryUnavailable as exc:
        log.warning("comparison_list_unavailable", error=str(exc)[:200])
        raise HTTPException(
            status_code=503, detail="Comparison history is unavailable"
        ) from exc


@router.get("/comparisons/{comparison_id}", response_model=ComparisonDetail)
def show_saved_comparison(comparison_id: int) -> ComparisonDetail:
    try:
        item = get_comparison(comparison_id)
    except ComparisonHistoryUnavailable as exc:
        log.warning("comparison_show_unavailable", error=str(exc)[:200])
        raise HTTPException(
            status_code=503, detail="Comparison history is unavailable"
        ) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return item
