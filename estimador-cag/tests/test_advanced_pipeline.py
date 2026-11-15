from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from generation.rag.retrieval.advanced_search_pipeline import (
    StageConfig,
    _chunk_key,
    _fuse_collection,
    advanced_retrieve,
)
from generation.rag.retrieval.collections import Collection
from generation.rag.retrieval.fusion import round_robin_merge
from generation.rag.retrieval.query_transform import DECOMPOSE, EXPAND, choose_technique
from generation.rag.retrieval.router import match_rules, route
from generation.rag.retrieval.search_pipeline import CollectionHits
from generation.rag.schemas import RetrievedChunk


def _chunk(chunk_id: int, collection: str = "budget", distance: float | None = 0.2):
    return RetrievedChunk(
        id=chunk_id,
        content=f"chunk-{chunk_id}",
        sector="ecommerce",
        project_year=2024,
        chunk_type="budget_component",
        distance=distance,
        collection=collection,
        has_vector_distance=distance is not None,
    )


def _hits(ids: list[int]) -> CollectionHits:
    return CollectionHits(
        collection=Collection.BUDGET,
        candidates={chunk_id: _chunk(chunk_id) for chunk_id in ids},
        vector_ids=ids,
        lexical_ids=[],
        candidates_evaluated=len(ids),
    )


def test_query_technique_and_rule_router_cover_spanish_and_english():
    assert choose_technique("oauth login") == "direct"
    assert choose_technique("Presupuesto histórico de checkout para Stripe") == EXPAND
    assert choose_technique("Budget, transcript and API integration details") == DECOMPOSE
    assert match_rules("presupuesto de checkout") == [Collection.BUDGET]
    assert match_rules("resumen de la reunión con el cliente") == [Collection.TRANSCRIPT]
    assert match_rules("documentación de API") == [Collection.TECHNICAL_DOC]


async def test_explicit_route_skips_classifier():
    decision = await route(
        "general query",
        explicit=[Collection.TRANSCRIPT, Collection.TRANSCRIPT],
        rules_enabled=True,
        classifier_enabled=True,
    )
    assert decision.targets == [Collection.TRANSCRIPT]
    assert decision.level == "explicit"


def test_differentiated_fusion_and_collection_key():
    # Expansion rewards consensus; decomposition preserves topical coverage.
    expanded = _fuse_collection(
        [_hits([1, 2, 3]), _hits([3, 4, 5])],
        technique=EXPAND,
        search_mode="vector",
        rrf_k=60,
    )
    decomposed = _fuse_collection(
        [_hits([1, 2, 3]), _hits([3, 4, 5])],
        technique=DECOMPOSE,
        search_mode="vector",
        rrf_k=60,
    )
    assert expanded[0].id == 3
    assert [chunk.id for chunk in decomposed] == [1, 3, 2, 4, 5]
    assert _chunk_key(_chunk(1, "budget")) != _chunk_key(_chunk(1, "transcript"))
    assert round_robin_merge([[1], [2, 3]]) == [1, 2, 3]


def test_fusion_preserves_a_valid_vector_score_across_query_variants():
    lexical_only = CollectionHits(
        collection=Collection.BUDGET,
        candidates={7: _chunk(7, distance=None)},
        vector_ids=[],
        lexical_ids=[7],
        candidates_evaluated=1,
    )
    vector_hit = CollectionHits(
        collection=Collection.BUDGET,
        candidates={7: _chunk(7, distance=0.4)},
        vector_ids=[7],
        lexical_ids=[],
        candidates_evaluated=1,
    )
    fused = _fuse_collection(
        [lexical_only, vector_hit],
        technique=EXPAND,
        search_mode="hybrid",
        rrf_k=60,
    )
    assert fused[0].has_vector_distance is True
    assert fused[0].distance == 0.4


async def test_advanced_search_reuses_hybrid_recall_and_marks_lexical_only(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class Store:
        def __init__(self):
            self.vector_args = None
            self.lexical_args = None

        async def search_filtered(self, _session, **kwargs):
            self.vector_args = kwargs
            return [self._row(1, 0.2, 10)], 1

        async def search_lexical(self, _session, **kwargs):
            self.lexical_args = kwargs
            return [self._row(2, 9.0, 20), self._row(1, 9.0, 10)]

        @staticmethod
        def _row(chunk_id, distance, hours):
            return SimpleNamespace(
                id=chunk_id,
                content=f"chunk-{chunk_id}",
                chunk_type="budget_component",
                metadata_={
                    "client_sector": "finance",
                    "year": 2024,
                    "budget_id": f"B-{chunk_id}",
                    "estimated_hours": hours,
                },
                distance=distance,
            )

    store = Store()
    monkeypatch.setattr("dependencies.get_chunk_store", lambda: store)
    monkeypatch.setattr("dependencies.get_async_session_factory", lambda: Session)
    outcome = await advanced_retrieve(
        query_text="budget integration with Stripe",
        embedder=SimpleNamespace(embed_one=lambda _text: [0.0] * 1536),
        stages=StageConfig(
            query_transform_enabled=False,
            search_mode="hybrid",
            rerank=False,
            temporal_decay_enabled=False,
        ),
        explicit_collections=[Collection.BUDGET],
        reference_date=date(2025, 1, 1),
    )
    by_id = {chunk.id: chunk for chunk in outcome.chunks}
    assert by_id[1].estimated_hours == 10
    assert by_id[1].has_vector_distance is True
    assert by_id[2].estimated_hours == 20
    assert by_id[2].distance is None
    assert by_id[2].has_vector_distance is False
    assert store.vector_args["document_types"] == [
        "historical_budget",
        "historical_task_breakdown",
    ]
    assert store.lexical_args["chunk_types"] == ["budget_component", "historical_task"]
