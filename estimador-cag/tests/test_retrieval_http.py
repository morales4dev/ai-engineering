"""HTTP tests for ``POST /v1/retrieval/search``. Pipeline is stubbed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import routers.retrieval as retrieval_router
import routers.security as security
from generation.rag.errors import RetrievalError
from generation.rag.schemas import RetrievalResult, RetrievedChunk
from main import app

RET_KEY = "retrieval-http-secret"


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: type("S", (), {"RETRIEVAL_API_KEY": RET_KEY, "ESTIMATE_API_KEY": "e"})(),
    )
    monkeypatch.setattr(
        retrieval_router,
        "get_embedder",
        lambda: type("E", (), {"embed_one": staticmethod(lambda t: [0.0] * 1536)})(),
    )

    async def fake_search(query_embedding, **kwargs):
        return RetrievalResult(
            chunks=[
                RetrievedChunk(
                    id=1,
                    content="Checkout 140h",
                    sector="ecommerce",
                    project_year=2024,
                    chunk_type="budget_component",
                    distance=0.3,
                )
            ],
            low_confidence=False,
            candidates_evaluated=7,
        )

    monkeypatch.setattr(retrieval_router, "search_chunks", fake_search)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _h():
    return {"X-API-Key": RET_KEY}


def test_retrieval_returns_chunks(client):
    r = client.post(
        "/v1/retrieval/search",
        json={"query_text": "ecommerce storefront with card checkout"},
        headers=_h(),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["chunks"]) == 1
    assert body["low_confidence"] is False


def test_retrieval_soft_fail_is_200(client, monkeypatch):
    async def empty_search(query_embedding, **kwargs):
        return RetrievalResult(chunks=[], low_confidence=True, candidates_evaluated=9)

    monkeypatch.setattr(retrieval_router, "search_chunks", empty_search)
    r = client.post(
        "/v1/retrieval/search",
        json={"query_text": "a quantum blockchain for dog grooming"},
        headers=_h(),
    )
    assert r.status_code == 200
    assert r.json()["low_confidence"] is True
    assert r.json()["chunks"] == []


def test_retrieval_short_query_is_422(client):
    r = client.post(
        "/v1/retrieval/search",
        json={"query_text": "short"},
        headers=_h(),
    )
    assert r.status_code == 422


def test_retrieval_store_failure_is_502(client, monkeypatch):
    async def boom(query_embedding, **kwargs):
        raise RetrievalError("pgvector down")

    monkeypatch.setattr(retrieval_router, "search_chunks", boom)
    r = client.post(
        "/v1/retrieval/search",
        json={"query_text": "ecommerce storefront with card checkout"},
        headers=_h(),
    )
    assert r.status_code == 502
