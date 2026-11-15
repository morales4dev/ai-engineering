"""HTTP contract for the new wizard and the retained one-shot endpoint."""

import pytest
from fastapi.testclient import TestClient

import routers.rag_estimate as estimate_router
from generation.rag.schemas import Estimate
from main import app
from routers import security
from services import rag_runs
from services.estimation_runs import EstimationRunsUnavailable


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setattr(
        security, "get_settings",
        lambda: type("S", (), {"RETRIEVAL_API_KEY": "retrieval", "ESTIMATE_API_KEY": "estimate"})(),
    )
    return TestClient(app)


def test_wizard_auth_and_end_to_end(client):
    headers = {"X-API-Key": "estimate"}
    assert client.post("/v1/estimate/runs", json={"transcript": "x" * 200}).status_code == 401
    run = client.post(
        "/v1/estimate/runs", json={"transcript": "x" * 200}, headers=headers
    ).json()
    run_id = run["id"]
    generated = client.post(f"/v1/estimate/runs/{run_id}/generate", headers=headers)
    assert generated.status_code == 200
    modules = generated.json()["structure"]["modules"]
    hours = client.post(
        f"/v1/estimate/runs/{run_id}/hours", json={"modules": modules}, headers=headers
    )
    assert hours.status_code == 200
    assert hours.json()["task_hours"]["tasks"][1]["estimated_hours"] is None
    invalid = client.patch(
        f"/v1/estimate/runs/{run_id}/verify",
        json={"modules": [{"name": "Checkout", "tasks": [{"name": "Cart",
               "estimated_hours": None, "rate_eur_per_hour": 75}]}]}, headers=headers,
    )
    assert invalid.status_code == 422
    verified = client.patch(
        f"/v1/estimate/runs/{run_id}/verify",
        json={"modules": [{"name": "Checkout", "tasks": [{"name": "Cart",
               "estimated_hours": 10, "rate_eur_per_hour": 80}]}]}, headers=headers,
    )
    assert verified.status_code == 200
    assert verified.json()["adjusted_breakdown"]["total_cost_eur"] == 800
    assert client.post(f"/v1/estimate/runs/{run_id}/retrieve", headers=headers).status_code == 404


def test_one_shot_stays_available(client, monkeypatch):
    async def estimate(transcript, idempotency_key=None):
        return Estimate(confidence="insufficient", reasoning="no evidence",
                        insufficient_context_explanation="no evidence")

    monkeypatch.setattr(estimate_router, "estimate_from_transcript", estimate)
    response = client.post(
        "/v1/estimate/from-transcript", json={"transcript": "x" * 200},
        headers={"X-API-Key": "estimate"},
    )
    assert response.status_code == 200
    assert response.json()["total_engineer_days"] is None


def test_standalone_task_hours_requires_key_and_does_not_create_run(client, store):
    payload = {"modules": [{"name": "Checkout", "tasks": [{"name": "Cart"}]}]}
    assert client.post("/v1/estimate/tasks/hours", json=payload).status_code == 401
    response = client.post(
        "/v1/estimate/tasks/hours", json=payload, headers={"X-API-Key": "estimate"}
    )
    assert response.status_code == 200
    assert response.json()["tasks"][0]["estimated_hours"] == 40
    assert store.rows == {}


def test_store_failure_is_visible(client, monkeypatch):
    def fail(**_kwargs):
        raise EstimationRunsUnavailable("postgres down")

    monkeypatch.setattr(rag_runs.runs_store, "list_runs", fail)
    assert client.get("/v1/estimate/runs", headers={"X-API-Key": "estimate"}).status_code == 503


@pytest.fixture
def store(monkeypatch):
    from test_rag_runs import InMemoryRuns

    from generation.rag.schemas import EstimationQuery
    from generation.rag.wizard import StructureEstimate, TaskHours

    fake = InMemoryRuns()
    monkeypatch.setattr(rag_runs, "runs_store", fake)

    async def reformulate(_transcript):
        return EstimationQuery(function="online store")

    async def structure(_query):
        return StructureEstimate(confidence="medium", reasoning="brief", modules=[
            {"name": "Checkout", "tasks": [{"name": "Cart"}, {"name": "Payment"}]}
        ])

    async def hours(_request):
        return [TaskHours(module="Checkout", task="Cart", has_match=True, estimated_hours=40),
                TaskHours(module="Checkout", task="Payment", has_match=False)]

    monkeypatch.setattr(rag_runs, "reformulate_query", reformulate)
    monkeypatch.setattr(rag_runs, "generate_structure", structure)
    monkeypatch.setattr(rag_runs, "estimate_tasks", hours)
    return fake
