"""HTTP tests for wizard ejecuciones (``/v1/estimate/runs``).

Adapted from Lidr ``test_estimate_stages.py``. Downstream work (LLM, embeddings,
pgvector, Postgres) is stubbed at the facade/pipeline boundary. Do not assert
``/stages/``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import routers.rag_estimate as estimate_router
import routers.retrieval as retrieval_router
import routers.security as security
from generation.rag.errors import GenerationError
from generation.rag.schemas import (
    Estimate,
    EstimationQuery,
    RetrievalResult,
    RetrievedChunk,
    SourceCitation,
)
from main import app
from services import rag_runs
from services.estimation_runs import EstimationRunsUnavailable
from test_rag_runs import InMemoryRuns

EST_KEY = "estimate-secret"
RET_KEY = "retrieval-secret"


def _chunk(cid: int, content: str = "Auth & RBAC component: ~12 engineer-days.") -> RetrievedChunk:
    return RetrievedChunk(
        id=cid,
        content=content,
        sector="ecommerce",
        project_year=2024,
        chunk_type="budget_component",
        distance=0.3,
    )


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    store = InMemoryRuns()
    monkeypatch.setattr(rag_runs, "runs_store", store)
    monkeypatch.setattr(
        rag_runs,
        "get_settings",
        lambda: SimpleNamespace(
            RETRIEVAL_TOP_K=10,
            RETRIEVAL_DISTANCE_THRESHOLD=0.6,
            MAX_CONTEXT_TOKENS=100_000,
        ),
    )
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: type("S", (), {"RETRIEVAL_API_KEY": RET_KEY, "ESTIMATE_API_KEY": EST_KEY})(),
    )

    async def fake_reformulate(transcript):
        return EstimationQuery(function="online store with card checkout", sector="ecommerce")

    async def fake_search(query_embedding, **kwargs):
        return RetrievalResult(
            chunks=[_chunk(1), _chunk(2)],
            low_confidence=False,
            candidates_evaluated=12,
        )

    async def fake_generate(context_block, structured_query):
        return Estimate(
            total_engineer_days=18,
            duration_weeks=4,
            sources=[SourceCitation(source_id=1, relevance="primary", used_for="auth")],
            confidence="high",
            reasoning="grounded",
        )

    monkeypatch.setattr(rag_runs, "reformulate_query", fake_reformulate)
    monkeypatch.setattr(
        rag_runs, "compose_search_text", lambda q: "online store card checkout ecommerce"
    )
    monkeypatch.setattr(
        rag_runs,
        "get_embedder",
        lambda: type("E", (), {"embed_one": staticmethod(lambda t: [0.0] * 1536)})(),
    )
    monkeypatch.setattr(rag_runs, "search_chunks", fake_search)
    monkeypatch.setattr(rag_runs, "generate_estimate", fake_generate)
    monkeypatch.setattr(
        rag_runs,
        "get_token_encoder",
        lambda: SimpleNamespace(encode=lambda text: list(text)),
    )
    yield store


@pytest.fixture
def client():
    return TestClient(app)


def _h(key=EST_KEY):
    return {"X-API-Key": key}


_TRANSCRIPT = {"transcript": "x" * 200}


def _create(client) -> dict:
    r = client.post("/v1/estimate/runs", json=_TRANSCRIPT, headers=_h())
    assert r.status_code == 200, r.text
    return r.json()


# --- auth boundary ---------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/v1/estimate/runs", _TRANSCRIPT),
        ("GET", "/v1/estimate/runs", None),
        ("GET", "/v1/estimate/runs/1", None),
        ("POST", "/v1/estimate/runs/1/reformulate", None),
        ("POST", "/v1/estimate/runs/1/retrieve", {}),
        ("POST", "/v1/estimate/runs/1/assemble", {}),
        ("POST", "/v1/estimate/runs/1/generate", None),
        ("PATCH", "/v1/estimate/runs/1/verify", {"modules": []}),
    ],
)
def test_runs_require_estimate_key(client, method, path, body):
    call = getattr(client, method.lower())
    kwargs = {"headers": _h(RET_KEY)}
    if body is not None:
        kwargs["json"] = body
    assert call(path).status_code == 401
    assert call(path, **kwargs).status_code == 401


def test_stages_path_is_not_mounted(client):
    r = client.post("/v1/estimate/stages/reformulate", json=_TRANSCRIPT, headers=_h())
    assert r.status_code == 404


# --- create / reformulate --------------------------------------------------


def test_create_run_returns_reformulation(client):
    body = _create(client)
    assert body["status"] == "reformulated"
    assert body["current_step"] == "reformulation"
    assert body["reformulation"]["query"]["sector"] == "ecommerce"
    assert body["reformulation"]["search_text"]


def test_reformulate_clears_later_steps(client):
    created = _create(client)
    run_id = created["id"]
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h()).status_code == 200
    assert client.post(f"/v1/estimate/runs/{run_id}/assemble", json={}, headers=_h()).status_code == 200
    r = client.post(f"/v1/estimate/runs/{run_id}/reformulate", headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert body["reformulation"]["search_text"]
    assert body["retrieval"] == {}
    assert body["augmentation"] == {}
    assert body["generation"] == {}


# --- retrieve --------------------------------------------------------------


def test_retrieve_persists_chunks_on_the_run(client):
    run_id = _create(client)["id"]
    r = client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert len(body["retrieval"]["chunks"]) == 2
    assert body["retrieval"]["low_confidence"] is False
    assert body["status"] == "retrieved"


def test_retrieve_soft_fail_passthrough(client, monkeypatch):
    async def empty_search(query_embedding, **kwargs):
        return RetrievalResult(chunks=[], low_confidence=True, candidates_evaluated=9)

    monkeypatch.setattr(rag_runs, "search_chunks", empty_search)
    run_id = _create(client)["id"]
    r = client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h())
    assert r.status_code == 200
    body = r.json()["retrieval"]
    assert body["chunks"] == []
    assert body["low_confidence"] is True


def test_retrieve_without_reformulation_is_409(client, stub):
    inserted = stub.insert(transcript="x" * 200)
    r = client.post(f"/v1/estimate/runs/{inserted.id}/retrieve", json={}, headers=_h())
    assert r.status_code == 409


# --- assemble --------------------------------------------------------------


def test_assemble_wraps_chunks_in_xml(client):
    run_id = _create(client)["id"]
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h()).status_code == 200
    r = client.post(f"/v1/estimate/runs/{run_id}/assemble", json={}, headers=_h())
    assert r.status_code == 200
    body = r.json()
    block = body["augmentation"]["context_block"]
    assert '<source id="1"' in block
    assert body["augmentation"]["dropped_count"] == 0
    assert body["augmentation"]["token_count"] > 0
    assert len(body["augmentation"]["kept_chunks"]) == 2


def test_assemble_drops_chunks_over_budget(client, monkeypatch):
    async def fat_search(query_embedding, **kwargs):
        return RetrievalResult(
            chunks=[_chunk(i, content="word " * 300) for i in range(1, 6)],
            low_confidence=False,
            candidates_evaluated=5,
        )

    monkeypatch.setattr(rag_runs, "search_chunks", fat_search)
    run_id = _create(client)["id"]
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h()).status_code == 200
    r = client.post(
        f"/v1/estimate/runs/{run_id}/assemble",
        json={"max_context_tokens": 300},
        headers=_h(),
    )
    assert r.status_code == 200
    body = r.json()["augmentation"]
    assert body["dropped_count"] > 0
    assert len(body["kept_chunks"]) < 5


# --- generate (real validate_citations + check_coherence via the facade) ---


def test_generate_flags_fabricated_citations(client, monkeypatch):
    estimate = Estimate(
        confidence="high",
        reasoning="r",
        sources=[
            SourceCitation(source_id=1, relevance="primary", used_for="auth"),
            SourceCitation(source_id=999, relevance="supporting", used_for="ghost"),
        ],
    )

    async def fake_generate(context_block, structured_query):
        return estimate

    monkeypatch.setattr(rag_runs, "generate_estimate", fake_generate)
    run_id = _create(client)["id"]
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h()).status_code == 200
    assert client.post(f"/v1/estimate/runs/{run_id}/assemble", json={}, headers=_h()).status_code == 200
    r = client.post(f"/v1/estimate/runs/{run_id}/generate", headers=_h())
    assert r.status_code == 200
    gen = r.json()["generation"]
    assert gen["fabricated_source_ids"] == [999]
    assert gen["coherent"] is True


def test_generate_flags_incoherent_insufficient(client, monkeypatch):
    estimate = Estimate(
        confidence="insufficient",
        reasoning="r",
        total_engineer_days=40,
        insufficient_context_explanation="should not have numbers",
    )

    async def fake_generate(context_block, structured_query):
        return estimate

    monkeypatch.setattr(rag_runs, "generate_estimate", fake_generate)
    run_id = _create(client)["id"]
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h()).status_code == 200
    assert client.post(f"/v1/estimate/runs/{run_id}/assemble", json={}, headers=_h()).status_code == 200
    r = client.post(f"/v1/estimate/runs/{run_id}/generate", headers=_h())
    assert r.status_code == 200
    assert r.json()["generation"]["coherent"] is False


def test_generate_pipeline_failure_is_502(client, monkeypatch):
    async def boom(context_block, structured_query):
        raise GenerationError("llm down")

    monkeypatch.setattr(rag_runs, "generate_estimate", boom)
    run_id = _create(client)["id"]
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h()).status_code == 200
    assert client.post(f"/v1/estimate/runs/{run_id}/assemble", json={}, headers=_h()).status_code == 200
    r = client.post(f"/v1/estimate/runs/{run_id}/generate", headers=_h())
    assert r.status_code == 502


# --- verify / get / list / errors ------------------------------------------


def test_verify_recomputes_total(client):
    run_id = _create(client)["id"]
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", json={}, headers=_h()).status_code == 200
    assert client.post(f"/v1/estimate/runs/{run_id}/assemble", json={}, headers=_h()).status_code == 200
    generated = client.post(f"/v1/estimate/runs/{run_id}/generate", headers=_h())
    assert generated.status_code == 200
    model_days = generated.json()["generation"]["estimate"]["total_engineer_days"]

    r = client.patch(
        f"/v1/estimate/runs/{run_id}/verify",
        json={
            "modules": [
                {
                    "name": "Checkout",
                    "tasks": [{"name": "Cart", "engineer_days": 10, "sources": [1]}],
                },
                {
                    "name": "Auth",
                    "tasks": [{"name": "Login", "engineer_days": 5, "sources": []}],
                },
            ]
        },
        headers=_h(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "verified"
    assert body["adjusted_breakdown"]["total_engineer_days"] == 15
    assert body["generation"]["estimate"]["total_engineer_days"] == model_days


def test_get_and_list(client):
    first = _create(client)
    second = _create(client)
    shown = client.get(f"/v1/estimate/runs/{first['id']}", headers=_h())
    assert shown.status_code == 200
    assert shown.json()["id"] == first["id"]
    listed = client.get("/v1/estimate/runs", headers=_h())
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert ids[0] == second["id"]
    assert first["id"] in ids


def test_missing_run_is_404(client):
    r = client.get("/v1/estimate/runs/999", headers=_h())
    assert r.status_code == 404
    r2 = client.post("/v1/estimate/runs/999/reformulate", headers=_h())
    assert r2.status_code == 404


def test_store_down_is_503(client, monkeypatch):
    def boom(*args, **kwargs):
        raise EstimationRunsUnavailable("postgres down")

    monkeypatch.setattr(rag_runs.runs_store, "list_runs", boom)
    r = client.get("/v1/estimate/runs", headers=_h())
    assert r.status_code == 503


# --- existing S09 endpoints still authenticate -----------------------------


def test_existing_endpoints_still_work(client, monkeypatch):
    async def fake_estimate(transcript, idempotency_key=None):
        return Estimate(
            confidence="insufficient",
            reasoning="stub",
            insufficient_context_explanation="stub",
        )

    async def fake_search(query_embedding, **kwargs):
        return RetrievalResult(chunks=[], low_confidence=True, candidates_evaluated=0)

    monkeypatch.setattr(
        retrieval_router,
        "get_embedder",
        lambda: type("E", (), {"embed_one": staticmethod(lambda t: [0.0] * 1536)})(),
    )
    monkeypatch.setattr(retrieval_router, "search_chunks", fake_search)
    monkeypatch.setattr(estimate_router, "estimate_from_transcript", fake_estimate)

    r1 = client.post(
        "/v1/retrieval/search",
        json={"query_text": "ecommerce storefront checkout"},
        headers=_h(RET_KEY),
    )
    r2 = client.post("/v1/estimate/from-transcript", json=_TRANSCRIPT, headers=_h(EST_KEY))
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_openapi_documents_new_and_old_paths(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/retrieval/search" in paths
    assert "/v1/estimate/from-transcript" in paths
    assert "/v1/estimate/runs" in paths
    assert "/v1/estimate/runs/{run_id}" in paths
    assert "/v1/estimate/runs/{run_id}/reformulate" in paths
    assert "/v1/estimate/runs/{run_id}/retrieve" in paths
    assert "/v1/estimate/runs/{run_id}/assemble" in paths
    assert "/v1/estimate/runs/{run_id}/generate" in paths
    assert "/v1/estimate/runs/{run_id}/verify" in paths
    assert "/search" in paths
    assert "/api/v1/estimate" in paths
    assert not any("/stages/" in path for path in paths)
