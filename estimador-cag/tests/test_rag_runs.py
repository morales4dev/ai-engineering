"""Tests of the persisted structure-and-hours wizard."""

from datetime import UTC, datetime

import pytest

from generation.rag.schemas import EstimationQuery
from generation.rag.wizard import (
    CostModule,
    StructureEstimate,
    StructureRequest,
    TaskHours,
    WizardRun,
)
from services import rag_runs
from services.estimation_runs import RunNotFound


class InMemoryRuns:
    def __init__(self):
        self.rows = {}

    def insert(self, *, transcript, idempotency_key=None):
        now = datetime.now(UTC)
        run = WizardRun(
            id=len(self.rows) + 1, transcript=transcript, status="started",
            current_step="transcript", workflow_version="s10", created_at=now,
            updated_at=now, idempotency_key=idempotency_key,
        )
        self.rows[run.id] = run
        return run

    def get(self, run_id):
        return self.rows.get(run_id)

    def list_runs(self, limit=20):
        return list(reversed(list(self.rows.values())))[:limit]

    def update(self, run_id, **fields):
        run = self.get(run_id)
        if run is None:
            raise RunNotFound(run_id)
        self.rows[run_id] = run.model_copy(update=fields)
        return self.rows[run_id]

@pytest.fixture
def store(monkeypatch):
    fake = InMemoryRuns()
    monkeypatch.setattr(rag_runs, "runs_store", fake)

    async def reformulate(_transcript):
        return EstimationQuery(function="online store")

    async def structure(_query):
        return StructureEstimate(
            confidence="medium", reasoning="brief", modules=[
                {"name": "Checkout", "tasks": [{"name": "Cart"}, {"name": "Payment"}]}
            ]
        )

    async def hours(_request):
        return [
            TaskHours(module="Checkout", task="Cart", has_match=True,
                      estimated_hours=40, reliability=0.8),
            TaskHours(module="Checkout", task="Payment", has_match=False),
        ]

    monkeypatch.setattr(rag_runs, "reformulate_query", reformulate)
    monkeypatch.setattr(rag_runs, "generate_structure", structure)
    monkeypatch.setattr(rag_runs, "estimate_tasks", hours)
    return fake


async def test_structure_hours_and_human_confirmation(store):
    run = await rag_runs.create_run("x" * 200)
    run = await rag_runs.generate(run.id)
    assert run.current_step == "review"
    assert run.structure["modules"][0]["tasks"][0]["name"] == "Cart"
    request = StructureRequest(modules=run.structure["modules"])
    run = await rag_runs.estimate_hours(run.id, request)
    tasks = run.adjusted_breakdown["modules"][0]["tasks"]
    assert tasks[0]["estimated_hours"] == 40
    assert tasks[1]["estimated_hours"] is None
    assert run.task_hours["tasks"][1]["has_match"] is False
    modules = [CostModule(name="Checkout", tasks=[
        {"name": "Cart", "estimated_hours": 20, "rate_eur_per_hour": 80},
        {"name": "Payment", "estimated_hours": 3, "rate_eur_per_hour": 50},
    ])]
    run = await rag_runs.verify(run.id, modules)
    assert run.adjusted_breakdown["total_hours"] == 23
    assert run.adjusted_breakdown["total_cost_eur"] == 1750
    assert run.adjusted_breakdown["confirmed_at"]


async def test_regeneration_invalidates_previous_hours(store):
    run = await rag_runs.create_run("x" * 200)
    run = await rag_runs.generate(run.id)
    run = await rag_runs.estimate_hours(run.id, StructureRequest(modules=run.structure["modules"]))
    run = await rag_runs.generate(run.id)
    assert run.task_hours == {}
    assert run.adjusted_breakdown == {}


async def test_legacy_runs_cannot_be_modified(store):
    run = store.insert(transcript="x" * 200)
    store.update(run.id, workflow_version="legacy", generation={"old": "data"})
    with pytest.raises(rag_runs.RunStepConflict):
        await rag_runs.generate(run.id)
    assert store.get(run.id).generation == {"old": "data"}


async def test_confirmation_requires_hours_stage(store):
    run = await rag_runs.create_run("x" * 200)
    with pytest.raises(rag_runs.RunStepConflict):
        await rag_runs.verify(run.id, [])
