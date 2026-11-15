"""Estimate each reviewed task from nearby historical task chunks."""

from __future__ import annotations

import asyncio
import statistics

from dependencies import get_embedder, get_runtime_retrieval_config
from generation.rag.chunk_types import HISTORICAL_TASK
from generation.rag.errors import RetrievalError
from generation.rag.retriever import search_chunks
from generation.rag.wizard import StructureRequest, TaskHours, TaskNeighbor


def consensus(neighbors: list[TaskNeighbor]) -> tuple[int, float, float]:
    weights = [1 / (0.001 + n.distance) for n in neighbors]
    total_weight = sum(weights)
    hours = sum(w * n.estimated_hours for w, n in zip(weights, neighbors)) / total_weight
    similarity = sum(w * max(0.0, 1 - n.distance) for w, n in zip(weights, neighbors))
    values = [n.estimated_hours for n in neighbors]
    mean = statistics.fmean(values)
    dispersion = statistics.pstdev(values) / mean if len(values) > 1 and mean > 0 else 0.0
    reliability = similarity / total_weight * (1 - min(dispersion, 1))
    return round(hours), round(reliability, 3), round(dispersion, 3)


async def estimate_tasks(request: StructureRequest) -> list[TaskHours]:
    embedder = get_embedder()
    if embedder is None:
        raise RetrievalError("Embedding service is not available.")

    runtime = get_runtime_retrieval_config()
    top_k = request.top_k if request.top_k is not None else runtime.effective_task_hours_top_k()
    threshold = (
        request.distance_threshold
        if request.distance_threshold is not None
        else runtime.effective_task_hours_distance_threshold()
    )
    mode = (
        request.search_mode
        if request.search_mode is not None
        else runtime.effective_search_mode()
    )
    rerank = request.rerank if request.rerank is not None else runtime.effective_rerank()
    semaphore = asyncio.Semaphore(5)

    async def estimate(module, task) -> TaskHours:
        text = f"Module: {module.name}\nTask: {task.name}\n{task.description or ''}"
        async with semaphore:
            try:
                embedding = await asyncio.to_thread(embedder.embed_one, text)
            except Exception as exc:
                raise RetrievalError("Task embedding failed.") from exc
            result = await search_chunks(
                embedding,
                query_text=text,
                top_k=top_k,
                rerank_top_n=top_k,
                distance_threshold=threshold,
                search_mode=mode,
                rerank=rerank,
                chunk_types=[HISTORICAL_TASK],
            )
        neighbors = [
            TaskNeighbor(
                source_id=chunk.id,
                budget_id=chunk.budget_id,
                estimated_hours=chunk.estimated_hours,
                distance=chunk.distance,
            )
            for chunk in result.chunks
            if chunk.estimated_hours is not None
            and chunk.has_vector_distance
            and chunk.distance is not None
            and chunk.distance <= threshold
            and chunk.distance >= 0
        ]
        if not neighbors:
            return TaskHours(module=module.name, task=task.name, has_match=False)
        hours, reliability, dispersion = consensus(neighbors)
        return TaskHours(
            module=module.name,
            task=task.name,
            has_match=True,
            estimated_hours=hours,
            reliability=reliability,
            dispersion=dispersion,
            neighbors=neighbors,
        )

    return list(await asyncio.gather(
        *(estimate(module, task) for module in request.modules for task in module.tasks)
    ))
