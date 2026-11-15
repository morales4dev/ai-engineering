from types import SimpleNamespace

import pytest

from generation.rag import task_hours
from generation.rag.wizard import StructureRequest, TaskNeighbor


@pytest.fixture
def runtime(monkeypatch):
    config = SimpleNamespace(
        effective_task_hours_top_k=lambda: 7,
        effective_task_hours_distance_threshold=lambda: 0.3,
        effective_search_mode=lambda: "hybrid",
        effective_rerank=lambda: True,
    )
    monkeypatch.setattr(task_hours, "get_runtime_retrieval_config", lambda: config)
    return config


def test_consensus_weights_nearest_and_penalizes_disagreement():
    neighbors = [
        TaskNeighbor(source_id=1, estimated_hours=50, distance=0.02),
        TaskNeighbor(source_id=2, estimated_hours=30, distance=0.4),
    ]
    hours, reliability, dispersion = task_hours.consensus(neighbors)
    assert 45 < hours <= 50
    assert 0 < reliability < 1
    assert dispersion > 0


async def test_task_search_excludes_lexical_only_and_missing_hours(monkeypatch, runtime):
    monkeypatch.setattr(task_hours, "get_embedder", lambda: SimpleNamespace(embed_one=lambda _: [0]))

    async def search(_embedding, **kwargs):
        assert kwargs["chunk_types"] == ["historical_task"]
        return SimpleNamespace(chunks=[
            SimpleNamespace(id=1, budget_id="b", estimated_hours=50, distance=1.0,
                            has_vector_distance=False),
            SimpleNamespace(id=2, budget_id="b", estimated_hours=None, distance=0.1,
                            has_vector_distance=True),
        ])

    monkeypatch.setattr(task_hours, "search_chunks", search)
    request = StructureRequest(
        modules=[{"name": "Auth", "tasks": [{"name": "Login"}]}],
        search_mode="hybrid", distance_threshold=2.0,
    )
    result = await task_hours.estimate_tasks(request)
    assert not result[0].has_match
    assert result[0].estimated_hours is None


async def test_task_search_uses_runtime_settings_unless_explicit(monkeypatch, runtime):
    monkeypatch.setattr(task_hours, "get_embedder", lambda: SimpleNamespace(embed_one=lambda _: [0]))
    calls = []

    async def search(_embedding, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(chunks=[])

    monkeypatch.setattr(task_hours, "search_chunks", search)
    modules = [{"name": "Auth", "tasks": [{"name": "Login"}]}]
    await task_hours.estimate_tasks(StructureRequest(modules=modules))
    await task_hours.estimate_tasks(StructureRequest(
        modules=modules, top_k=2, distance_threshold=0.6, search_mode="vector", rerank=False,
    ))
    assert [calls[0][key] for key in ("top_k", "distance_threshold", "search_mode", "rerank")] == [
        7, 0.3, "hybrid", True,
    ]
    assert [calls[1][key] for key in ("top_k", "distance_threshold", "search_mode", "rerank")] == [
        2, 0.6, "vector", False,
    ]


def test_structure_rejects_duplicate_tasks():
    with pytest.raises(ValueError, match="unique"):
        StructureRequest(modules=[{
            "name": "Auth", "tasks": [{"name": "Login"}, {"name": "Login"}],
        }])
