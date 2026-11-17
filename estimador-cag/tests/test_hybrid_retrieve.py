from __future__ import annotations

from types import SimpleNamespace

import pytest

from generation.rag.retrieval import search_pipeline


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
        metadata_={
            "client_sector": "ecommerce",
            "year": 2024,
            "budget_id": f"BUD-{chunk_id}",
            "estimated_hours": 12,
        },
        distance=0.2 + chunk_id / 100,
    )


class FakeReranker:
    def rerank(self, _query, candidates, *, top_n):
        return sorted(candidates, key=lambda candidate: candidate.id, reverse=True)[:top_n]


@pytest.fixture
def store(monkeypatch):
    instance = FakeStore()
    monkeypatch.setattr(search_pipeline, "get_chunk_store", lambda: instance)
    monkeypatch.setattr(search_pipeline, "get_async_session_factory", lambda: lambda: FakeSession())
    return instance


async def test_hybrid_reranking_recalls_both_branches_and_returns_top_n(store):
    result = await search_pipeline.retrieve(
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
    assert result.chunks[0].estimated_hours == 12
    assert result.chunks[0].distance == 1.0
    assert result.chunks[0].has_vector_distance is False
    assert result.chunks[1].distance == pytest.approx(0.22)
    assert result.chunks[1].has_vector_distance is True


async def test_vector_mode_does_not_run_lexical_branch(store):
    result = await search_pipeline.retrieve(
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


@pytest.mark.parametrize(("key", "document_id"), [
    ("source_id", "SOURCE-1"), ("transcript_id", "TR-1"), ("doc_id", "DOC-1"),
])
def test_non_budget_provenance_survives_context_assembly(key, document_id):
    from generation.rag.context_assembler import build_context_block

    row = _row(1)
    row.metadata_ = {key: document_id}
    row.chunk_type = "meeting_segment" if key == "transcript_id" else "doc_section"
    chunk = search_pipeline._row_to_chunk(row, distance=None)
    assert f'document_id="{document_id}"' in build_context_block([chunk])
