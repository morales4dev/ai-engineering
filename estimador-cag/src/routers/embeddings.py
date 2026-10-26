"""HTTP layer for the embedding pipeline.

Thin router: it maps service exceptions to status codes. The chunk → embed →
persist orchestration lives in ``RagIngestService``; no business logic here.
Compare / list / show stay on this router and are unchanged.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from dependencies import (
    ALL_STRATEGIES,
    build_chunkers,
    get_embedder,
    get_rag_ingest_service,
)
from generation.rag.analysis.comparison import (
    ChunkingComparator,
    CompareRequest,
    CompareResponse,
    ComparisonDetail,
    ComparisonListResponse,
)
from generation.rag.embedding.embedder import OpenAIEmbedder
from generation.rag.ingest_service import DuplicateDocumentError, RagIngestService
from generation.rag.schemas import IngestRequest, IngestResponse
from services.comparisons import (
    ComparisonHistoryUnavailable,
    get_comparison,
    list_comparisons,
    persist_comparison,
)

log = structlog.get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    responses={409: {"description": "Document already ingested"}},
)
async def ingest(
    request: IngestRequest,
    service: RagIngestService | None = Depends(get_rag_ingest_service),
) -> IngestResponse | JSONResponse:
    """Persist one budget as a document + embedded chunks (one transaction)."""
    if service is None:
        # No OPENAI_API_KEY configured. Generic message to the client, detail logged.
        log.error("embeddings_ingest_failed", reason="embedder_unavailable")
        raise HTTPException(status_code=500, detail="Embedding service is not available.")

    log.info(
        "embeddings_ingest_received",
        source_path=request.source_path,
        document_type=request.document_type,
    )
    try:
        return await service.ingest(
            source_path=request.source_path,
            document_type=request.document_type,
            budget=request.content,
        )
    except DuplicateDocumentError as exc:
        # JSONResponse (not HTTPException) to keep the exercise's literal
        # top-level shape: {"detail": ..., "document_id": ...}.
        log.info(
            "embeddings_ingest_duplicate",
            source_path=request.source_path,
            document_id=exc.document_id,
        )
        return JSONResponse(
            status_code=409,
            content={"detail": "Document already ingested", "document_id": exc.document_id},
        )
    except Exception as exc:  # noqa: BLE001 — embedding/DB failures become a 500.
        log.error(
            "embeddings_ingest_failed",
            reason="ingest_error",
            error_type=type(exc).__name__,
            error=str(exc)[:300],
        )
        raise HTTPException(status_code=500, detail="Failed to generate embeddings.") from exc


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
