"""Query transformation, collection routing, hybrid fusion, and temporal ranking."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import date

import structlog

from config import Settings
from generation.rag.errors import RetrievalError
from generation.rag.retrieval.collections import (
    Collection,
    HardFilters,
)
from generation.rag.retrieval.fusion import reciprocal_rank_fusion, round_robin_merge
from generation.rag.retrieval.pipeline import CollectionHits, hybrid_search_one
from generation.rag.retrieval.query_transform import DECOMPOSE, SubQuery, transform_query
from generation.rag.retrieval.router import RoutingDecision, route
from generation.rag.retrieval.temporal import apply_temporal_decay
from generation.rag.schemas import RetrievedChunk

log = structlog.get_logger()


@dataclass(frozen=True)
class StageConfig:
    routing_enabled: bool = True
    query_transform_enabled: bool = True
    search_mode: str = "hybrid"
    rerank: bool = False
    temporal_decay_enabled: bool = False
    top_k: int = 5
    recall_k: int = 50
    distance_threshold: float = 0.6
    rrf_k: int = 60
    half_life_days: int = 900
    max_subqueries: int = 4
    max_targets: int = 3
    router_model: str | None = None
    query_transform_model: str | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        search_mode: str | None = None,
        rerank: bool | None = None,
        routing_enabled: bool | None = None,
        query_transform_enabled: bool | None = None,
        temporal_decay_enabled: bool | None = None,
        top_k: int | None = None,
        distance_threshold: float | None = None,
    ) -> StageConfig:
        return cls(
            routing_enabled=(
                settings.RETRIEVAL_ROUTING_ENABLED
                if routing_enabled is None
                else routing_enabled
            ),
            query_transform_enabled=(
                settings.QUERY_TRANSFORM_ENABLED
                if query_transform_enabled is None
                else query_transform_enabled
            ),
            search_mode=search_mode or settings.RETRIEVAL_SEARCH_MODE,
            rerank=settings.RERANKER_ENABLED if rerank is None else rerank,
            temporal_decay_enabled=(
                settings.TEMPORAL_DECAY_ENABLED
                if temporal_decay_enabled is None
                else temporal_decay_enabled
            ),
            top_k=top_k if top_k is not None else settings.RERANK_TOP_N,
            recall_k=settings.RETRIEVAL_RECALL_TOP_K,
            distance_threshold=(
                settings.RETRIEVAL_DISTANCE_THRESHOLD
                if distance_threshold is None
                else distance_threshold
            ),
            rrf_k=settings.RRF_K,
            half_life_days=settings.TEMPORAL_DECAY_HALF_LIFE_DAYS,
            max_subqueries=settings.QUERY_MAX_SUBQUERIES,
            max_targets=settings.ROUTER_MAX_TARGETS,
            router_model=settings.ROUTER_MODEL,
            query_transform_model=settings.QUERY_TRANSFORM_MODEL,
        )


@dataclass
class AdvancedRetrievalOutcome:
    chunks: list[RetrievedChunk]
    routing: RoutingDecision
    technique: str
    subqueries: list[SubQuery]
    cardinality: dict[str, int] = field(default_factory=dict)
    low_confidence: bool = True


def _chunk_key(chunk: RetrievedChunk) -> tuple[str | None, int]:
    return chunk.collection, chunk.id


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, value))))


def _fuse_collection(
    hits_per_subquery: list[CollectionHits],
    *,
    technique: str,
    search_mode: str,
    rrf_k: int,
) -> list[RetrievedChunk]:
    candidates: dict[int, RetrievedChunk] = {}
    for hits in hits_per_subquery:
        for chunk_id, candidate in hits.candidates.items():
            previous = candidates.get(chunk_id)
            if previous is None or (
                candidate.has_vector_distance and not previous.has_vector_distance
            ):
                candidates[chunk_id] = candidate
    rankings = [
        hits.fused_order(search_mode=search_mode, rrf_k=rrf_k)
        for hits in hits_per_subquery
    ]
    if technique == DECOMPOSE:
        return round_robin_merge(rankings, key=lambda chunk: chunk.id)
    fused = reciprocal_rank_fusion(
        [[chunk.id for chunk in ordered] for ordered in rankings], k=rrf_k
    )
    return [candidates[chunk_id] for chunk_id, _score in fused]


async def advanced_retrieve(
    *,
    query_text: str,
    embedder,
    stages: StageConfig,
    explicit_collections: list[Collection] | None = None,
    hard_filters: HardFilters | None = None,
    reference_date: date,
    reranker=None,
) -> AdvancedRetrievalOutcome:
    """Run advanced retrieval without changing the existing single-index API."""
    if stages.search_mode not in {"vector", "hybrid"}:
        raise ValueError("search_mode must be 'vector' or 'hybrid'")
    from dependencies import get_async_session_factory, get_chunk_store

    try:
        plan, routing = await asyncio.gather(
            transform_query(
                query_text,
                enabled=stages.query_transform_enabled,
                model=stages.query_transform_model,
                max_subqueries=stages.max_subqueries,
            ),
            route(
                query_text,
                explicit=explicit_collections,
                rules_enabled=stages.routing_enabled,
                classifier_enabled=stages.routing_enabled,
                max_targets=stages.max_targets,
                model=stages.router_model,
            ),
        )
        embeddings = await asyncio.gather(
            *(asyncio.to_thread(embedder.embed_one, subquery.query) for subquery in plan.subqueries)
        )
    except Exception as exc:
        log.error("advanced_query_preparation_failed", error_type=type(exc).__name__)
        raise RetrievalError("Failed to prepare advanced retrieval queries.") from exc

    store = get_chunk_store()
    session_factory = get_async_session_factory()
    hard_filters = hard_filters or HardFilters()

    async def search_one(collection: Collection, subquery: SubQuery, embedding) -> CollectionHits:
        async with session_factory() as session:
            return await hybrid_search_one(
                session,
                store,
                collection=collection,
                query_embedding=embedding,
                query_text=subquery.query,
                search_mode=stages.search_mode,
                recall_k=stages.recall_k,
                top_k=stages.top_k,
                distance_threshold=stages.distance_threshold,
                will_rerank=stages.rerank,
                hard_filters=hard_filters,
            )

    try:
        flat = await asyncio.gather(
            *(
                search_one(collection, subquery, embedding)
                for collection in routing.targets
                for subquery, embedding in zip(plan.subqueries, embeddings)
            )
        )
    except Exception as exc:
        log.error("advanced_search_failed", error_type=type(exc).__name__, error=str(exc)[:200])
        raise RetrievalError("Vector store query failed.") from exc

    per_collection: dict[Collection, list[CollectionHits]] = {
        collection: [] for collection in routing.targets
    }
    offset = 0
    for collection in routing.targets:
        per_collection[collection].extend(flat[offset : offset + len(plan.subqueries)])
        offset += len(plan.subqueries)

    cardinality = {}
    collection_orders = []
    for collection, hits in per_collection.items():
        cardinality[collection.value] = hits[0].candidates_evaluated if hits else 0
        ordered = _fuse_collection(
            hits,
            technique=plan.technique,
            search_mode=stages.search_mode,
            rrf_k=stages.rrf_k,
        )
        if ordered:
            collection_orders.append(ordered)
    pool = round_robin_merge(collection_orders, key=_chunk_key)[: stages.recall_k]

    if stages.rerank and pool:
        try:
            if reranker is None:
                from dependencies import get_reranker

                reranker = get_reranker()
            scores = await asyncio.to_thread(
                reranker.score, query_text, [chunk.content for chunk in pool]
            )
            if len(scores) != len(pool):
                raise ValueError("reranker returned a mismatched score count")
            scored = [(chunk, _sigmoid(float(score))) for chunk, score in zip(pool, scores)]
            scored.sort(key=lambda pair: pair[1], reverse=True)
        except Exception as exc:
            log.error("advanced_reranking_failed", error_type=type(exc).__name__)
            raise RetrievalError("Cross-encoder reranking failed.") from exc
    else:
        scored = [(chunk, 1.0 / (index + 1)) for index, chunk in enumerate(pool)]

    if stages.temporal_decay_enabled:
        scored = apply_temporal_decay(
            scored, half_life_days=stages.half_life_days, reference_date=reference_date
        )
    final = [
        chunk.model_copy(update={"relevance_score": score})
        for chunk, score in scored[: stages.top_k]
    ]
    log.info(
        "advanced_retrieve_done",
        technique=plan.technique,
        routing_level=routing.level,
        targets=[target.value for target in routing.targets],
        subqueries=len(plan.subqueries),
        pool=len(pool),
        results=len(final),
    )
    return AdvancedRetrievalOutcome(
        chunks=final,
        routing=routing,
        technique=plan.technique,
        subqueries=plan.subqueries,
        cardinality=cardinality,
        low_confidence=not final,
    )
