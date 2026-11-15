#!/usr/bin/env python3
"""Measure precision@5 and warm query latency for the four S10 configurations.

Run with the historical budget corpus ingested and OPENAI_API_KEY configured.
Embedding and one-time cross-encoder loading are excluded from query latency.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import get_settings
from dependencies import get_embedder, get_reranker
from generation.rag.retrieval.pipeline import retrieve

GOLDEN_PATH = ROOT / "evals" / "golden_retrieval.json"
CONFIGS = (
    ("A", "vector", False),
    ("B", "hybrid", False),
    ("C", "vector", True),
    ("D", "hybrid", True),
)
MEASURED_RUNS = 3


def precision_at_k(chunks, relevant_ids: set[str], k: int) -> float:
    return sum(chunk.budget_id in relevant_ids for chunk in chunks[:k]) / k


async def main() -> None:
    settings = get_settings()
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    queries = golden["queries"]
    k = int(golden.get("k", 5))
    chunk_types = golden.get("chunk_types")
    embedder = get_embedder()
    if embedder is None:
        raise RuntimeError("OPENAI_API_KEY is required to embed the golden queries.")

    embeddings = {
        item["id"]: await asyncio.to_thread(embedder.embed_one, item["query"])
        for item in queries
    }
    reranker = get_reranker()
    await asyncio.to_thread(reranker.load)
    results = {name: {"precision": [], "latency": []} for name, *_ in CONFIGS}

    for name, search_mode, rerank in CONFIGS:
        for item in queries:
            args = {
                "query_embedding": embeddings[item["id"]],
                "query_text": item["query"],
                "search_mode": search_mode,
                "rerank": rerank,
                "top_k": k,
                "recall_k": settings.RETRIEVAL_RECALL_TOP_K,
                "rerank_top_n": k,
                "distance_threshold": 2.0,
                "rrf_k": settings.RRF_K,
                "chunk_types": chunk_types,
                "reranker": reranker,
            }
            await retrieve(**args)
            samples = []
            last = None
            for _ in range(MEASURED_RUNS):
                started = time.perf_counter()
                last = await retrieve(**args)
                samples.append((time.perf_counter() - started) * 1000)
            if not last.chunks:
                raise RuntimeError(
                    f"{name}/{item['id']} returned no chunks; verify the corpus is ingested."
                )
            results[name]["precision"].append(
                precision_at_k(last.chunks, set(item["relevant_budget_ids"]), k)
            )
            results[name]["latency"].extend(samples)

    print("| Config | Search | Reranking | Precision@5 | Latency (ms) |")
    print("| --- | --- | --- | ---: | ---: |")
    for name, search_mode, rerank in CONFIGS:
        bucket = results[name]
        print(
            f"| {name} | {search_mode} | {'Yes' if rerank else 'No'} | "
            f"{statistics.fmean(bucket['precision']):.2f} | "
            f"{statistics.fmean(bucket['latency']):.1f} |"
        )


if __name__ == "__main__":
    asyncio.run(main())
