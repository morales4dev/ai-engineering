from __future__ import annotations

from types import SimpleNamespace

import pytest

from generation.rag.retrieval import pipeline


class FakeStore:
    def __init__(self):
        self.vector_calls = []
        self.lexical_calls = []

    async def search_filtered(self, _session, **kwargs):
        self.vector_calls.append(kwargs)
        return [_row(1), _row(2)], 12

    async def search_lexical(self, _session, **kwargs):
        self.lexical_calls.append(kwargs)
        return [_row(3), _row(1)]


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


def _row(chunk_id: int):
    return SimpleNamespace(
        id=chunk_id,
        content=f"chunk-{chunk_id}",
        chunk_type="budget_component",
        metadata_={"client_sector": "ecommerce", "year": 2024, "budget_id": f"BUD-{chunk_id}"},
        distance=0.2 + chunk_id / 100,
    )


class FakeReranker:
    def rerank(self, _query, candidates, *, top_n):
        return sorted(candidates, key=lambda candidate: candidate.id, reverse=True)[:top_n]


@pytest.fixture
def store(monkeypatch):
    instance = FakeStore()
    monkeypatch.setattr(pipeline, "get_chunk_store", lambda: instance)
    monkeypatch.setattr(pipeline, "get_async_session_factory", lambda: lambda: FakeSession())
    return instance


async def test_hybrid_reranking_recalls_both_branches_and_returns_top_n(store):
    result = await pipeline.retrieve(
        query_embedding=[0.0] * 1536,
        query_text="ecommerce checkout",
        search_mode="hybrid",
        rerank=True,
        top_k=5,
        recall_k=50,
        rerank_top_n=2,
        distance_threshold=0.6,
        rrf_k=60,
        reranker=FakeReranker(),
    )

    assert store.vector_calls[0]["top_k"] == 50
    assert store.lexical_calls[0]["top_k"] == 50
    assert [chunk.id for chunk in result.chunks] == [3, 2]
    assert result.chunks[0].budget_id == "BUD-3"


async def test_vector_mode_does_not_run_lexical_branch(store):
    result = await pipeline.retrieve(
        query_embedding=[0.0] * 1536,
        query_text="ecommerce checkout",
        search_mode="vector",
        rerank=False,
        top_k=1,
        recall_k=50,
        rerank_top_n=5,
        distance_threshold=0.6,
        rrf_k=60,
    )

    assert [chunk.id for chunk in result.chunks] == [1]
    assert store.vector_calls[0]["top_k"] == 1
    assert store.lexical_calls == []
