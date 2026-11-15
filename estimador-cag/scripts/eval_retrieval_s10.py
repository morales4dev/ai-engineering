#!/usr/bin/env python3
"""Compare Session 10 retrieval configurations against the annotated corpus.

Requires the budget, transcript and technical-document samples to be ingested.
Latency includes embeddings and, where applicable, LLM and reranker calls.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dependencies import get_embedder, get_reranker
from generation.rag.retrieval.advanced_search_pipeline import StageConfig, advanced_retrieve
from generation.rag.retrieval.collections import Collection

GOLDEN_PATH = ROOT / "evals" / "golden_retrieval.json"
MEASURED_RUNS = 3


@dataclass(frozen=True)
class NamedConfig:
    name: str
    label: str
    stages: StageConfig
    collections: list[Collection] | None


def _config(name: str, label: str, *, multi_index: bool = False, **kwargs) -> NamedConfig:
    defaults = {
        "routing_enabled": False,
        "query_transform_enabled": False,
        "search_mode": "vector",
        "rerank": False,
        "temporal_decay_enabled": False,
        "distance_threshold": 2.0,
    }
    defaults.update(kwargs)
    return NamedConfig(
        name, label, StageConfig(**defaults), None if multi_index else [Collection.BUDGET]
    )


CONFIGS = (
    _config("A", "Vector"),
    _config("B", "Hybrid", search_mode="hybrid"),
    _config("C", "Vector + rerank", rerank=True),
    _config("D", "Hybrid + rerank", search_mode="hybrid", rerank=True),
    _config("E", "Hybrid + rerank + temporal", search_mode="hybrid", rerank=True,
            temporal_decay_enabled=True),
    _config("F", "Multi-index routing", search_mode="hybrid", rerank=True, multi_index=True,
            routing_enabled=True),
    _config("G", "Query transform", search_mode="hybrid", rerank=True,
            query_transform_enabled=True),
    _config("H", "Full pipeline", search_mode="hybrid", rerank=True, multi_index=True,
            routing_enabled=True, query_transform_enabled=True, temporal_decay_enabled=True),
)


def precision_at_k(chunks, relevant_ids: set[str], k: int) -> float:
    return sum((chunk.source_id or chunk.budget_id) in relevant_ids for chunk in chunks[:k]) / k


async def main() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    queries, k = golden["queries"], int(golden.get("k", 5))
    embedder = get_embedder()
    if embedder is None:
        raise RuntimeError("OPENAI_API_KEY is required to embed the golden queries.")
    reranker = get_reranker()
    await asyncio.to_thread(reranker.load)
    reference_date = datetime.now(UTC).date()
    results = {cfg.name: {"precision": [], "latency": [], "per_query": {}} for cfg in CONFIGS}
    empty = False

    for cfg in CONFIGS:
        for item in queries:
            kwargs = {
                "query_text": item["query"], "embedder": embedder,
                "stages": replace(cfg.stages, top_k=k),
                "explicit_collections": cfg.collections, "reference_date": reference_date,
                "reranker": reranker,
            }
            await advanced_retrieve(**kwargs)
            samples = []
            for _ in range(MEASURED_RUNS):
                started = time.perf_counter()
                outcome = await advanced_retrieve(**kwargs)
                samples.append((time.perf_counter() - started) * 1000)
            empty |= not outcome.chunks
            relevant = set(item.get("relevant_source_ids") or item["relevant_budget_ids"])
            precision = precision_at_k(outcome.chunks, relevant, k)
            results[cfg.name]["precision"].append(precision)
            results[cfg.name]["latency"].extend(samples)
            results[cfg.name]["per_query"][item["id"]] = precision

    print(f"| Config | Stages | Precision@{k} | Latency (ms) |")
    print("| --- | --- | ---: | ---: |")
    for cfg in CONFIGS:
        bucket = results[cfg.name]
        print(f"| {cfg.name} | {cfg.label} | {statistics.fmean(bucket['precision']):.2f} | "
              f"{statistics.fmean(bucket['latency']):.1f} |")
    print("\n| Query | " + " | ".join(cfg.name for cfg in CONFIGS) + " |")
    print("| --- | " + " | ".join("---:" for _ in CONFIGS) + " |")
    for item in queries:
        print("| " + " | ".join(
            [item["id"]] + [f"{results[cfg.name]['per_query'][item['id']]:.2f}"
                            for cfg in CONFIGS]
        ) + " |")
    if empty:
        print("WARNING: some queries returned no chunks; verify all corpora are ingested.",
              file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
