"""Advanced multi-collection retrieval endpoint; the S09 route remains unchanged."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from config import get_settings
from dependencies import get_embedder, get_runtime_retrieval_config
from generation.rag.errors import RetrievalError
from generation.rag.retrieval.advanced_pipeline import StageConfig, advanced_retrieve
from generation.rag.retrieval.collections import Collection, HardFilters
from generation.rag.schemas import RetrievedChunk
from routers.rate_limiting import limiter
from routers.security import require_retrieval_key

log = structlog.get_logger()

router = APIRouter(prefix="/v1/retrieval", tags=["retrieval"])


class AdvancedRetrievalRequest(BaseModel):
    query_text: str = Field(min_length=10, max_length=2000)
    collections: list[Collection] | None = None
    top_k: int = Field(default=5, ge=1, le=30)
    technologies: list[str] | None = None
    sectors: list[str] | None = None
    min_date: date | None = None
    doc_version: str | None = Field(default=None, max_length=50)
    search_mode: Literal["vector", "hybrid"] | None = None
    rerank: bool | None = None
    routing_enabled: bool | None = None
    query_transform_enabled: bool | None = None
    temporal_decay_enabled: bool | None = None
    distance_threshold: float | None = Field(default=None, ge=0.0, le=2.0)


class RoutingInfo(BaseModel):
    level: str
    targets: list[str]
    reason: str


class SubQueryInfo(BaseModel):
    topic: str
    query: str


class AdvancedRetrievalResult(BaseModel):
    chunks: list[RetrievedChunk]
    low_confidence: bool
    routing: RoutingInfo
    technique: str
    subqueries: list[SubQueryInfo]
    cardinality: dict[str, int]


@router.post(
    "/advanced-search",
    response_model=AdvancedRetrievalResult,
    dependencies=[Depends(require_retrieval_key)],
)
@limiter.limit("120/minute")
async def advanced_search(
    request: Request, payload: AdvancedRetrievalRequest
) -> AdvancedRetrievalResult:
    embedder = get_embedder()
    if embedder is None:
        raise HTTPException(status_code=500, detail="Embedding service is not available.")

    runtime = get_runtime_retrieval_config()
    stages = StageConfig.from_settings(
        get_settings(),
        search_mode=payload.search_mode or runtime.effective_search_mode(),
        rerank=(
            payload.rerank
            if payload.rerank is not None
            else runtime.effective_rerank()
        ),
        routing_enabled=(
            payload.routing_enabled
            if payload.routing_enabled is not None
            else runtime.effective_routing()
        ),
        query_transform_enabled=(
            payload.query_transform_enabled
            if payload.query_transform_enabled is not None
            else runtime.effective_query_transform()
        ),
        temporal_decay_enabled=(
            payload.temporal_decay_enabled
            if payload.temporal_decay_enabled is not None
            else runtime.effective_temporal_decay()
        ),
        top_k=payload.top_k,
        distance_threshold=payload.distance_threshold,
    )
    try:
        outcome = await advanced_retrieve(
            query_text=payload.query_text,
            embedder=embedder,
            stages=stages,
            explicit_collections=payload.collections,
            hard_filters=HardFilters(
                technologies=tuple(payload.technologies or ()),
                sectors=tuple(payload.sectors or ()),
                min_date=payload.min_date,
                version=payload.doc_version,
            ),
            reference_date=datetime.now(UTC).date(),
        )
    except RetrievalError as exc:
        raise HTTPException(status_code=502, detail="Retrieval failed.") from exc
    except Exception as exc:
        log.error(
            "advanced_retrieval_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:300],
        )
        raise HTTPException(status_code=502, detail="Failed to run advanced retrieval.") from exc

    return AdvancedRetrievalResult(
        chunks=outcome.chunks,
        low_confidence=outcome.low_confidence,
        routing=RoutingInfo(
            level=outcome.routing.level,
            targets=[target.value for target in outcome.routing.targets],
            reason=outcome.routing.reason,
        ),
        technique=outcome.technique,
        subqueries=[
            SubQueryInfo(topic=subquery.topic, query=subquery.query)
            for subquery in outcome.subqueries
        ],
        cardinality=outcome.cardinality,
    )
