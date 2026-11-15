"""Wizard facade for RAG ejecuciones.

Stand-in for Lidr's web: each mutating method calls the amnesiac pipeline
functions, writes ``estimation_runs``, and ``clear_downstream`` when an earlier
step is re-run. Persistence failure raises (503 at HTTP). Does not talk SQL
itself — that is ``services.estimation_runs``.

Generate follows Lidr's **stage** generate (no auto-retry; fabricated ids /
coherence land on the run payload). ``estimate_from_transcript`` stays on the
one-shot path only.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import structlog

from config import get_settings
from dependencies import get_embedder, get_token_encoder
from generation.rag.context_assembler import build_context_block, truncate_to_token_budget
from generation.rag.errors import RetrievalError
from generation.rag.estimator import generate_estimate
from generation.rag.observability import log_stage
from generation.rag.query_reformulator import compose_search_text, reformulate_query
from generation.rag.retriever import search_chunks
from generation.rag.schemas import (
    AssembleResult,
    Estimate,
    EstimationRun,
    GenerateResult,
    ReformulationResult,
    RetrievedChunk,
    RunRetrieveFilters,
    WorkModule,
)
from generation.rag.validation import check_coherence, validate_citations
from services import estimation_runs as runs_store
from services.estimation_runs import RunNotFound

log = structlog.get_logger()

_KNOWN_SECTORS = {"finance", "ecommerce", "healthcare", "industrial"}


class RunStepConflict(Exception):
    """An earlier wizard step has not been persisted yet."""

    def __init__(self, run_id: int, need: str) -> None:
        super().__init__(f"estimation run {run_id} is missing {need}")
        self.run_id = run_id
        self.need = need


def _load(run_id: int) -> EstimationRun:
    run = runs_store.get(run_id)
    if run is None:
        raise RunNotFound(run_id)
    return run


def _reformulation_of(run: EstimationRun) -> ReformulationResult:
    if not run.reformulation:
        raise RunStepConflict(run.id, "reformulation")
    return ReformulationResult.model_validate(run.reformulation)


def _chunks_of(run: EstimationRun) -> list[RetrievedChunk]:
    raw = run.retrieval.get("chunks")
    if not run.retrieval or raw is None:
        raise RunStepConflict(run.id, "retrieval")
    return [RetrievedChunk.model_validate(chunk) for chunk in raw]


def _augmentation_of(run: EstimationRun) -> AssembleResult:
    if not run.augmentation:
        raise RunStepConflict(run.id, "augmentation")
    return AssembleResult.model_validate(run.augmentation)


def _seed_adjusted_breakdown(estimate: Estimate) -> dict:
    modules = [
        {
            "name": module.name,
            "description": module.description or "",
            "tasks": [
                {
                    "name": task.name,
                    "description": task.description or "",
                    "engineer_days": task.engineer_days,
                    "sources": list(task.sources),
                }
                for task in module.tasks
            ],
        }
        for module in estimate.modules
    ]
    total = sum(task["engineer_days"] for module in modules for task in module["tasks"])
    return {
        "modules": modules,
        "total_engineer_days": total,
        "adjusted_at": None,
    }


def _resolved_filters(
    run: EstimationRun,
    filters: RunRetrieveFilters | None,
) -> dict:
    settings = get_settings()
    incoming = filters or RunRetrieveFilters()
    brief = _reformulation_of(run).query
    sector = brief.sector.lower().strip() if brief.sector else None
    default_sectors = [sector] if sector in _KNOWN_SECTORS else None
    sectors = incoming.sectors if incoming.sectors else default_sectors
    return {
        "top_k": incoming.top_k if incoming.top_k is not None else settings.RETRIEVAL_TOP_K,
        "distance_threshold": (
            incoming.distance_threshold
            if incoming.distance_threshold is not None
            else settings.RETRIEVAL_DISTANCE_THRESHOLD
        ),
        "sectors": sectors,
        "project_year_min": incoming.project_year_min,
        "project_year_max": incoming.project_year_max,
        "chunk_types": incoming.chunk_types if incoming.chunk_types else None,
    }


def _elapsed_ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def create_run(
    transcript: str, *, idempotency_key: str | None = None
) -> EstimationRun:
    """Insert the ejecución and immediately run reformulation."""
    inserted = runs_store.insert(transcript=transcript, idempotency_key=idempotency_key)
    return await reformulate(inserted.id)


async def reformulate(run_id: int) -> EstimationRun:
    run = _load(run_id)
    t0 = time.perf_counter()
    with log_stage("reformulation", str(run_id)):
        query = await reformulate_query(run.transcript)
        search_text = compose_search_text(query)
    payload = ReformulationResult(query=query, search_text=search_text).model_dump(mode="json")
    runs_store.update(
        run_id,
        reformulation=payload,
        status="reformulated",
        current_step="reformulation",
        duration_ms=_elapsed_ms(t0),
    )
    return runs_store.clear_downstream(run_id, "reformulation")


async def retrieve(run_id: int, filters: RunRetrieveFilters | None = None) -> EstimationRun:
    run = _load(run_id)
    brief = _reformulation_of(run)
    applied = _resolved_filters(run, filters)
    embedder = get_embedder()
    if embedder is None:
        raise RetrievalError("Embedding service is not available.")

    t0 = time.perf_counter()
    with log_stage("retrieval", str(run_id), sectors=applied["sectors"]):
        query_embedding = await asyncio.to_thread(embedder.embed_one, brief.search_text)
        result = await search_chunks(
            query_embedding,
            top_k=applied["top_k"],
            distance_threshold=applied["distance_threshold"],
            sectors=applied["sectors"],
            project_year_min=applied["project_year_min"],
            project_year_max=applied["project_year_max"],
            chunk_types=applied["chunk_types"],
        )
    payload = result.model_dump(mode="json")
    payload["filters"] = applied
    runs_store.update(
        run_id,
        retrieval=payload,
        status="retrieved",
        current_step="retrieval",
        duration_ms=_elapsed_ms(t0),
    )
    return runs_store.clear_downstream(run_id, "retrieval")


async def assemble(run_id: int, max_context_tokens: int | None = None) -> EstimationRun:
    run = _load(run_id)
    chunks = _chunks_of(run)
    settings = get_settings()
    budget = max_context_tokens or settings.MAX_CONTEXT_TOKENS
    encoder = get_token_encoder()

    t0 = time.perf_counter()
    with log_stage("augmentation", str(run_id), budget=budget):
        kept = truncate_to_token_budget(chunks, budget, encoder)
        context_block = build_context_block(kept)
        token_count = len(encoder.encode(context_block)) if context_block else 0
    payload = AssembleResult(
        context_block=context_block,
        kept_chunks=kept,
        dropped_count=len(chunks) - len(kept),
        token_count=token_count,
    ).model_dump(mode="json")
    runs_store.update(
        run_id,
        augmentation=payload,
        status="assembled",
        current_step="augmentation",
        duration_ms=_elapsed_ms(t0),
    )
    return runs_store.clear_downstream(run_id, "augmentation")


async def generate(run_id: int) -> EstimationRun:
    run = _load(run_id)
    query = _reformulation_of(run).query
    augmentation = _augmentation_of(run)

    t0 = time.perf_counter()
    with log_stage("generation", str(run_id), sources=len(augmentation.kept_chunks)):
        estimate = await generate_estimate(
            augmentation.context_block, structured_query=query
        )
    fabricated = validate_citations(estimate, augmentation.kept_chunks)
    coherent = check_coherence(estimate)
    payload = GenerateResult(
        estimate=estimate,
        fabricated_source_ids=fabricated,
        coherent=coherent,
    ).model_dump(mode="json")
    return runs_store.update(
        run_id,
        generation=payload,
        adjusted_breakdown=_seed_adjusted_breakdown(estimate),
        status="generated",
        current_step="generation",
        duration_ms=_elapsed_ms(t0),
    )


async def verify(run_id: int, modules: list[WorkModule]) -> EstimationRun:
    """Persist the human-edited table. Recompute total. Leave model output untouched."""
    _load(run_id)
    cleaned: list[dict] = []
    for module in modules:
        name = module.name.strip()
        if not name:
            continue
        tasks = []
        for task in module.tasks:
            task_name = task.name.strip()
            if not task_name:
                continue
            tasks.append(
                {
                    "name": task_name,
                    "description": (task.description or "").strip(),
                    "engineer_days": task.engineer_days,
                    "sources": list(task.sources),
                }
            )
        cleaned.append({"name": name, "description": (module.description or "").strip(), "tasks": tasks})
    total = sum(task["engineer_days"] for module in cleaned for task in module["tasks"])
    payload = {
        "modules": cleaned,
        "total_engineer_days": total,
        "adjusted_at": datetime.now(timezone.utc).isoformat(),
    }
    return runs_store.update(
        run_id,
        adjusted_breakdown=payload,
        status="verified",
        current_step="verification",
    )


def get(run_id: int) -> EstimationRun | None:
    return runs_store.get(run_id)


def list_runs(limit: int = 20) -> list[EstimationRun]:
    return runs_store.list_runs(limit=limit)
