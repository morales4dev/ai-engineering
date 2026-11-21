"""Flow tests for the end-to-end orchestrator (Session 9).

Every component is mocked: we validate the wiring (which stage runs, in what
order, and the soft-fail short-circuit), not the components themselves.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import dependencies as deps
from generation.rag import estimator as orch
from generation.rag.schemas import (
    Estimate,
    EstimationQuery,
    RetrievalResult,
    RetrievedChunk,
    SourceCitation,
    SourceReference,
    TaskItem,
    WorkModule,
)

_SETTINGS = SimpleNamespace(
    REFORMULATION_MODEL="gpt-5-mini",
    GENERATION_MODEL="gpt-5",
    GENERATION_REASONING_EFFORT="high",
    GENERATION_MAX_TOKENS=64_000,
    RETRIEVAL_TOP_K=10,
    RETRIEVAL_DISTANCE_THRESHOLD=0.6,
    MAX_CONTEXT_TOKENS=100_000,
)


class CharEncoder:
    def encode(self, text: str) -> list[str]:
        return list(text)


class RecordingStore:
    def __init__(self):
        self.saved: dict[str, Estimate] = {}

    def get(self, key):
        return self.saved.get(key)

    def set(self, key, estimate):
        self.saved[key] = estimate


def _chunk(chunk_id: int) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id,
        content="Component: Checkout\nEstimated hours: 140",
        sector="ecommerce",
        project_year=2024,
        chunk_type="budget_component",
        distance=0.42,
        budget_id="BUD-2024-005",
    )


def _good_estimate() -> Estimate:
    return Estimate(
        total_engineer_days=18,
        duration_weeks=4,
        modules=[
            WorkModule(
                name="Checkout",
                tasks=[TaskItem(
                    name="Cart & payment flow", engineer_days=18, grounded=True,
                    sources=[SourceReference(
                        chunk_id="1", document_id="BUD-2024-005", evidence="Estimated hours: 140",
                    )],
                )],
            )
        ],
        sources=[SourceCitation(source_id=1, relevance="primary", used_for="checkout")],
        assumptions=[],
        confidence="high",
        reasoning="Grounded in BUD-2024-005.",
    )


@pytest.fixture
def wire(monkeypatch):
    """Wire the orchestrator with mocked stages; return a call counter."""
    calls = {"reformulate": 0, "search": 0, "generate": 0, "embed": 0}
    store = RecordingStore()

    def _wire(*, retrieval: RetrievalResult, estimate: Estimate | None = None):
        async def fake_reformulate(transcript):
            calls["reformulate"] += 1
            return EstimationQuery(function="ecommerce storefront", sector="ecommerce")

        async def fake_search(query_embedding, **kwargs):
            calls["search"] += 1
            return retrieval

        async def fake_generate(context_block, structured_query):
            calls["generate"] += 1
            return estimate

        def fake_embed(text):
            calls["embed"] += 1
            return [0.0] * 1536

        monkeypatch.setattr(orch, "get_settings", lambda: _SETTINGS)
        monkeypatch.setattr(orch, "reformulate_query", fake_reformulate)
        monkeypatch.setattr(orch, "search_chunks", fake_search)
        monkeypatch.setattr(orch, "generate_estimate", fake_generate)
        monkeypatch.setattr(deps, "get_embedder", lambda: SimpleNamespace(embed_one=fake_embed))
        monkeypatch.setattr(deps, "get_token_encoder", lambda: CharEncoder())
        monkeypatch.setattr(deps, "get_idempotency_store", lambda: store)
        monkeypatch.setattr(
            deps, "get_runtime_retrieval_config",
            lambda: SimpleNamespace(
                effective_search_mode=lambda: "vector", effective_rerank=lambda: False,
                effective_augmentation=lambda: False, effective_hallucination_gate=lambda: False,
            ),
        )
        return calls, store

    return _wire


async def test_happy_path_runs_all_stages(wire):
    retrieval = RetrievalResult(chunks=[_chunk(1)], low_confidence=False, candidates_evaluated=5)
    calls, _store = wire(retrieval=retrieval, estimate=_good_estimate())

    result = await orch.estimate_from_transcript("x" * 200)

    assert result.confidence == "high"
    assert result.total_engineer_days == 18
    assert calls == {"reformulate": 1, "search": 1, "generate": 1, "embed": 1}


async def test_semantic_gate_attaches_reports_and_downgrades_unverified(wire, monkeypatch):
    from generation.rag.schemas import HallucinationReport, LineGate

    retrieval = RetrievalResult(chunks=[_chunk(1)], low_confidence=False, candidates_evaluated=1)
    wire(retrieval=retrieval, estimate=_good_estimate())
    monkeypatch.setattr(orch, "get_settings", lambda: SimpleNamespace(
        **vars(_SETTINGS), HALLUCINATION_NUMERIC_TOLERANCE=0.5,
    ))
    monkeypatch.setattr(deps, "get_runtime_retrieval_config", lambda: SimpleNamespace(
        effective_search_mode=lambda: "vector", effective_rerank=lambda: False,
        effective_augmentation=lambda: False, effective_hallucination_gate=lambda: True,
    ))
    monkeypatch.setattr(deps, "get_runtime_config", lambda: SimpleNamespace(
        effective=lambda _: "test-model",
    ))

    async def gate(estimate, chunks, **kwargs):
        return HallucinationReport(lines=[
            LineGate(module="Checkout", component="Cart", status="unverified", reason="offline"),
        ])

    monkeypatch.setattr(orch, "gate_estimate", gate)
    result = await orch.estimate_from_transcript("x" * 200)
    assert result.confidence == "low"
    assert result.citation_report.grounded_lines == 1
    assert result.hallucination_report.lines[0].status == "unverified"


async def test_soft_fail_skips_generation(wire):
    retrieval = RetrievalResult(chunks=[], low_confidence=True, candidates_evaluated=7)
    calls, _store = wire(retrieval=retrieval, estimate=_good_estimate())

    result = await orch.estimate_from_transcript("x" * 200)

    assert result.confidence == "insufficient"
    assert result.total_engineer_days is None
    assert result.insufficient_context_explanation
    assert calls["generate"] == 0  # generator never called on soft-fail


async def test_generate_estimate_passes_reasoning_token_budget(monkeypatch):
    """The grounded generator uses Responses with its reasoning/output ceiling."""
    captured: dict = {}

    def fake_complete_structured_responses(**kwargs):
        captured.update(kwargs)
        return _good_estimate(), {}

    wrapper = SimpleNamespace(complete_structured_responses=fake_complete_structured_responses)
    monkeypatch.setattr(orch, "get_settings", lambda: _SETTINGS)
    monkeypatch.setattr(deps, "get_llm_wrapper", lambda: wrapper)

    estimate = await orch.generate_estimate(
        '<source id="1">x</source>', EstimationQuery(function="ecommerce storefront")
    )

    assert estimate.confidence == "high"
    assert captured["max_tokens"] == _SETTINGS.GENERATION_MAX_TOKENS
    assert captured["reasoning_effort"] == "high"
    assert captured["model_override"] == "gpt-5"
    assert captured["response_model"] is Estimate


async def test_responses_generation_preserves_feedback_and_surfaces_failure(monkeypatch):
    from generation.rag.errors import GenerationError

    captured = {}
    failure = ValueError("Structured Responses output was refused.")

    def fail(**kwargs):
        captured.update(kwargs)
        raise failure

    monkeypatch.setattr(orch, "get_settings", lambda: _SETTINGS)
    monkeypatch.setattr(
        deps, "get_llm_wrapper", lambda: SimpleNamespace(complete_structured_responses=fail),
    )
    with pytest.raises(GenerationError) as caught:
        await orch._generate(
            '<source id="1">x</source>', EstimationQuery(function="checkout"),
            feedback="Only cite source 1.",
        )

    assert caught.value.__cause__ is failure
    assert "<correction>\nOnly cite source 1.\n</correction>" in captured["user_message"]


async def test_idempotency_hit_short_circuits_pipeline(wire):
    retrieval = RetrievalResult(chunks=[_chunk(1)], low_confidence=False, candidates_evaluated=5)
    calls, store = wire(retrieval=retrieval, estimate=_good_estimate())

    first = await orch.estimate_from_transcript("x" * 200, idempotency_key="k1")
    assert calls["generate"] == 1
    assert store.saved.get("k1") is not None

    second = await orch.estimate_from_transcript("x" * 200, idempotency_key="k1")
    assert second == first
    # No stage re-ran on the cached call.
    assert calls == {"reformulate": 1, "search": 1, "generate": 1, "embed": 1}


@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_citation_retry_is_bounded_and_logs_final_report(
    wire, monkeypatch, repair_succeeds,
):
    from structlog.testing import capture_logs

    bad = _good_estimate()
    bad.modules[0].tasks[0].sources[0].chunk_id = "invented"
    wire(
        retrieval=RetrievalResult(chunks=[_chunk(1)], low_confidence=False, candidates_evaluated=1),
        estimate=bad,
    )
    retries = []

    async def repair(context, query, *, feedback):
        retries.append(feedback)
        return _good_estimate() if repair_succeeds else bad

    monkeypatch.setattr(orch, "_generate", repair)
    monkeypatch.setattr(orch, "_current_request_id", lambda: "test-request")
    with capture_logs() as logs:
        result = await orch.estimate_from_transcript("x" * 200)

    assert len(retries) == 1
    assert "invented" in retries[0]
    assert result.confidence == ("high" if repair_succeeds else "low")
    reports = [entry for entry in logs if entry["event"] == "citation_report"]
    assert [entry["phase"] for entry in reports] == ["initial", "final"]
    assert all(entry["request_id"] == "test-request" for entry in reports)
    assert reports[-1]["dangling_lines"] == (0 if repair_succeeds else 1)
    assert any(e["event"] == "citations_unrepaired" for e in logs) is not repair_succeeds


async def test_coherence_repair_cannot_bypass_final_citation_check(wire, monkeypatch):
    incoherent = _good_estimate().model_copy(update={"confidence": "insufficient"})
    wire(
        retrieval=RetrievalResult(chunks=[_chunk(1)], low_confidence=False, candidates_evaluated=1),
        estimate=incoherent,
    )
    bad = _good_estimate()
    bad.modules[0].tasks[0].sources[0].chunk_id = "invented"

    async def repair(*args, **kwargs):
        return bad

    monkeypatch.setattr(orch, "_generate", repair)
    result = await orch.estimate_from_transcript("x" * 200)
    assert result.confidence == "low"


async def test_dropped_chunk_is_not_a_valid_citation(wire, monkeypatch):
    from generation.rag.context_assembler import build_context_block

    estimate = _good_estimate()
    estimate.modules[0].tasks[0].sources[0].chunk_id = "2"
    wire(
        retrieval=RetrievalResult(
            chunks=[_chunk(1), _chunk(2)], low_confidence=False, candidates_evaluated=2,
        ),
        estimate=estimate,
    )
    monkeypatch.setattr(
        orch, "get_settings",
        lambda: SimpleNamespace(
            **{**vars(_SETTINGS), "MAX_CONTEXT_TOKENS": len(build_context_block([_chunk(1)]))}
        ),
    )
    retries = []

    async def repair(context, query, *, feedback):
        retries.append(feedback)
        assert 'id="2"' not in context
        return _good_estimate()

    monkeypatch.setattr(orch, "_generate", repair)
    await orch.estimate_from_transcript("x" * 200)
    assert len(retries) == 1
