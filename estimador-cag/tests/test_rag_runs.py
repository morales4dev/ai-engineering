"""Facade tests for wizard ejecuciones. No FastAPI, no Postgres, no OpenAI."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from generation.rag.errors import RetrievalError
from generation.rag.schemas import (
    Estimate,
    EstimationQuery,
    EstimationRun,
    RetrievalResult,
    RetrievedChunk,
    RunRetrieveFilters,
    SourceCitation,
    TaskItem,
    WorkModule,
)
from services import rag_runs
from services.estimation_runs import RunNotFound


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryRuns:
    """Stand-in for ``services.estimation_runs`` (no Postgres)."""

    def __init__(self) -> None:
        self.rows: dict[int, EstimationRun] = {}
        self._n = 0

    def insert(self, *, transcript: str, idempotency_key: str | None = None) -> EstimationRun:
        self._n += 1
        now = _now()
        run = EstimationRun(
            id=self._n,
            transcript=transcript,
            status="started",
            current_step="transcript",
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        self.rows[self._n] = run
        return run

    def get(self, run_id: int) -> EstimationRun | None:
        return self.rows.get(run_id)

    def list_runs(self, limit: int = 20) -> list[EstimationRun]:
        ordered = sorted(self.rows.values(), key=lambda r: r.created_at, reverse=True)
        return ordered[:limit]

    def update(self, run_id: int, **fields) -> EstimationRun:
        run = self.rows.get(run_id)
        if run is None:
            raise RunNotFound(run_id)
        data = run.model_dump()
        data.update(fields)
        data["updated_at"] = _now()
        self.rows[run_id] = EstimationRun.model_validate(data)
        return self.rows[run_id]

    def clear_downstream(self, run_id: int, from_step: str) -> EstimationRun:
        from services.estimation_runs import _CLEAR_AFTER

        columns = _CLEAR_AFTER.get(from_step, ())
        if not columns:
            got = self.get(run_id)
            if got is None:
                raise RunNotFound(run_id)
            return got
        return self.update(run_id, **{column: {} for column in columns})


def _chunk(cid: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        id=cid,
        content="Component: Checkout\nEstimated hours: 140",
        sector="ecommerce",
        project_year=2024,
        chunk_type="budget_component",
        distance=0.42,
    )


def _good_estimate(*, source_id: int = 1) -> Estimate:
    return Estimate(
        total_engineer_days=18,
        duration_weeks=4,
        modules=[
            WorkModule(
                name="Checkout",
                tasks=[TaskItem(name="Cart", engineer_days=18, sources=[source_id])],
            )
        ],
        sources=[SourceCitation(source_id=source_id, relevance="primary", used_for="checkout")],
        assumptions=[],
        confidence="high",
        reasoning="Grounded.",
    )


@pytest.fixture
def store(monkeypatch):
    fake = InMemoryRuns()
    monkeypatch.setattr(rag_runs, "runs_store", fake)
    monkeypatch.setattr(
        rag_runs,
        "get_settings",
        lambda: SimpleNamespace(
            RETRIEVAL_TOP_K=10,
            RETRIEVAL_DISTANCE_THRESHOLD=0.6,
            MAX_CONTEXT_TOKENS=100_000,
        ),
    )
    return fake


@pytest.fixture
def pipeline(monkeypatch):
    calls = {"reformulate": 0, "search": 0, "generate": 0, "embed": 0}

    async def fake_reformulate(transcript):
        calls["reformulate"] += 1
        return EstimationQuery(function="ecommerce storefront", sector="ecommerce")

    async def fake_search(query_embedding, **kwargs):
        calls["search"] += 1
        calls["search_kwargs"] = kwargs
        return RetrievalResult(chunks=[_chunk(1)], low_confidence=False, candidates_evaluated=5)

    async def fake_generate(context_block, structured_query):
        calls["generate"] += 1
        return _good_estimate()

    monkeypatch.setattr(rag_runs, "reformulate_query", fake_reformulate)
    monkeypatch.setattr(rag_runs, "compose_search_text", lambda q: "ecommerce storefront")
    monkeypatch.setattr(rag_runs, "search_chunks", fake_search)
    monkeypatch.setattr(rag_runs, "generate_estimate", fake_generate)
    monkeypatch.setattr(
        rag_runs,
        "get_embedder",
        lambda: SimpleNamespace(embed_one=lambda text: [0.0] * 1536),
    )
    monkeypatch.setattr(
        rag_runs,
        "get_token_encoder",
        lambda: SimpleNamespace(encode=lambda text: list(text)),
    )
    return calls


async def test_create_run_inserts_and_reformulates(store, pipeline):
    run = await rag_runs.create_run("x" * 200)

    assert run.id == 1
    assert run.status == "reformulated"
    assert run.current_step == "reformulation"
    assert run.reformulation["query"]["sector"] == "ecommerce"
    assert run.reformulation["search_text"] == "ecommerce storefront"
    assert pipeline["reformulate"] == 1
    assert pipeline["generate"] == 0


async def test_retrieve_defaults_sector_from_brief(store, pipeline):
    created = await rag_runs.create_run("x" * 200)
    run = await rag_runs.retrieve(created.id)

    assert run.status == "retrieved"
    assert run.retrieval["chunks"][0]["id"] == 1
    assert run.retrieval["filters"]["sectors"] == ["ecommerce"]
    assert run.retrieval["filters"]["top_k"] == 10
    assert pipeline["search_kwargs"]["sectors"] == ["ecommerce"]


async def test_retrieve_explicit_filters_win(store, pipeline):
    created = await rag_runs.create_run("x" * 200)
    await rag_runs.retrieve(
        created.id,
        RunRetrieveFilters(top_k=3, sectors=["finance"], distance_threshold=0.4),
    )
    assert pipeline["search_kwargs"]["top_k"] == 3
    assert pipeline["search_kwargs"]["sectors"] == ["finance"]
    assert pipeline["search_kwargs"]["distance_threshold"] == 0.4


async def test_retrieve_without_reformulation_raises(store, pipeline):
    inserted = store.insert(transcript="x" * 200)
    with pytest.raises(rag_runs.RunStepConflict):
        await rag_runs.retrieve(inserted.id)


async def test_reformulate_clears_later_steps(store, pipeline):
    created = await rag_runs.create_run("x" * 200)
    await rag_runs.retrieve(created.id)
    await rag_runs.assemble(created.id)
    rerun = await rag_runs.reformulate(created.id)

    assert rerun.reformulation["search_text"] == "ecommerce storefront"
    assert rerun.retrieval == {}
    assert rerun.augmentation == {}
    assert rerun.generation == {}
    assert rerun.adjusted_breakdown == {}


async def test_generate_does_not_auto_retry_fabricated_ids(store, pipeline, monkeypatch):
    async def fake_generate(context_block, structured_query):
        pipeline["generate"] += 1
        return _good_estimate(source_id=99)

    monkeypatch.setattr(rag_runs, "generate_estimate", fake_generate)
    created = await rag_runs.create_run("x" * 200)
    await rag_runs.retrieve(created.id)
    await rag_runs.assemble(created.id)
    run = await rag_runs.generate(created.id)

    assert pipeline["generate"] == 1
    assert run.generation["fabricated_source_ids"] == [99]
    assert run.generation["coherent"] is True
    assert run.adjusted_breakdown["modules"][0]["name"] == "Checkout"
    assert run.adjusted_breakdown["adjusted_at"] is None
    # Model output stays even when citations are dirty.
    assert run.generation["estimate"]["total_engineer_days"] == 18


async def test_verify_recomputes_total_and_leaves_generation(store, pipeline):
    created = await rag_runs.create_run("x" * 200)
    await rag_runs.retrieve(created.id)
    await rag_runs.assemble(created.id)
    generated = await rag_runs.generate(created.id)
    model_days = generated.generation["estimate"]["total_engineer_days"]

    run = await rag_runs.verify(
        created.id,
        [
            WorkModule(
                name="Checkout",
                tasks=[TaskItem(name="Cart", engineer_days=10, sources=[1])],
            ),
            WorkModule(
                name="Auth",
                tasks=[TaskItem(name="Login", engineer_days=5, sources=[])],
            ),
        ],
    )
    assert run.status == "verified"
    assert run.current_step == "verification"
    assert run.adjusted_breakdown["total_engineer_days"] == 15
    assert run.generation["estimate"]["total_engineer_days"] == model_days
    assert run.adjusted_breakdown["adjusted_at"]


async def test_get_and_list(store, pipeline):
    first = await rag_runs.create_run("a" * 200)
    second = await rag_runs.create_run("b" * 200)
    assert rag_runs.get(first.id).id == first.id
    ids = [run.id for run in rag_runs.list_runs()]
    assert ids[0] == second.id
    assert first.id in ids


async def test_mutating_missing_run_raises(store, pipeline):
    with pytest.raises(RunNotFound):
        await rag_runs.reformulate(999)


async def test_retrieve_without_embedder_raises(store, pipeline, monkeypatch):
    created = await rag_runs.create_run("x" * 200)
    monkeypatch.setattr(rag_runs, "get_embedder", lambda: None)
    with pytest.raises(RetrievalError):
        await rag_runs.retrieve(created.id)
