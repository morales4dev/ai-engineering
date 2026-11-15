from __future__ import annotations

from generation.rag.schemas import RetrievalResult, RetrievedChunk
from generation.rag.task_hours import estimate_tasks
from generation.rag.wizard import StructureRequest


async def test_task_hours_rejects_lexical_candidate_even_when_threshold_is_one(monkeypatch):
    class Embedder:
        def embed_one(self, _text):
            return [0.0] * 1536

    async def lexical_only_result(*_args, **_kwargs):
        return RetrievalResult(
            chunks=[
                RetrievedChunk(
                    id=4,
                    content="lexical-only match",
                    sector="unknown",
                    project_year=0,
                    chunk_type="historical_task",
                    distance=1.0,
                    has_vector_distance=False,
                    estimated_hours=80,
                )
            ],
            low_confidence=False,
            candidates_evaluated=1,
        )

    monkeypatch.setattr("generation.rag.task_hours.get_embedder", lambda: Embedder())
    monkeypatch.setattr("generation.rag.task_hours.search_chunks", lexical_only_result)
    result = await estimate_tasks(
        StructureRequest(
            modules=[{"name": "Payments", "tasks": [{"name": "Stripe integration"}]}],
            top_k=5,
            distance_threshold=1.0,
            search_mode="hybrid",
            rerank=False,
        )
    )
    assert result[0].has_match is False
    assert result[0].estimated_hours is None
