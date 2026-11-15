from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import routers.retrieval_advanced as advanced_router
from generation.rag.retrieval.advanced_pipeline import AdvancedRetrievalOutcome
from generation.rag.retrieval.collections import Collection
from generation.rag.retrieval.query_transform import SubQuery
from generation.rag.retrieval.router import RoutingDecision
from generation.rag.schemas import RetrievedChunk
from main import app
from routers import security

RET_KEY = "advanced-retrieval-secret"


@pytest.fixture
def client(monkeypatch):
    settings = SimpleNamespace(
        RETRIEVAL_API_KEY=RET_KEY,
        RETRIEVAL_ROUTING_ENABLED=False,
        QUERY_TRANSFORM_ENABLED=False,
        RETRIEVAL_SEARCH_MODE="vector",
        RERANKER_ENABLED=False,
        TEMPORAL_DECAY_ENABLED=False,
        RERANK_TOP_N=5,
        RETRIEVAL_RECALL_TOP_K=20,
        RETRIEVAL_DISTANCE_THRESHOLD=0.6,
        RRF_K=60,
        TEMPORAL_DECAY_HALF_LIFE_DAYS=900,
        QUERY_MAX_SUBQUERIES=4,
        ROUTER_MAX_TARGETS=3,
        ROUTER_MODEL="gpt-4o-mini",
        QUERY_TRANSFORM_MODEL="gpt-4o-mini",
    )
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(advanced_router, "get_settings", lambda: settings)
    monkeypatch.setattr(
        advanced_router,
        "get_embedder",
        lambda: SimpleNamespace(embed_one=lambda _text: [0.0] * 1536),
    )

    async def fake_retrieve(**kwargs):
        return AdvancedRetrievalOutcome(
            chunks=[
                RetrievedChunk(
                    id=1,
                    content="Payment implementation, 20 hours",
                    sector="finance",
                    project_year=2024,
                    chunk_type="budget_component",
                    distance=None,
                    has_vector_distance=False,
                    estimated_hours=20,
                    collection="budget",
                )
            ],
            routing=RoutingDecision([Collection.BUDGET], "explicit", "caller choice"),
            technique="direct",
            subqueries=[SubQuery(topic="original", query=kwargs["query_text"])],
            cardinality={"budget": 1},
            low_confidence=False,
        )

    monkeypatch.setattr(advanced_router, "advanced_retrieve", fake_retrieve)
    with TestClient(app) as test_client:
        yield test_client


def test_advanced_search_returns_routing_and_vector_validity(client):
    response = client.post(
        "/v1/retrieval/advanced-search",
        headers={"X-API-Key": RET_KEY},
        json={
            "query_text": "How many hours for payment integration?",
            "collections": ["budget"],
            "top_k": 3,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["routing"]["targets"] == ["budget"]
    assert result["chunks"][0]["estimated_hours"] == 20
    assert result["chunks"][0]["has_vector_distance"] is False
    assert result["chunks"][0]["distance"] is None


def test_advanced_search_keeps_retrieval_auth(client):
    response = client.post(
        "/v1/retrieval/advanced-search",
        json={"query_text": "How many hours for payment integration?"},
    )
    assert response.status_code == 401
