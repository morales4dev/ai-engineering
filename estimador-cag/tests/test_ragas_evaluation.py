from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import structlog
from pydantic import ValidationError

from generation.rag.context_assembler import build_context_block
from generation.rag.schemas import Estimate, EstimationQuery, RetrievalResult, RetrievedChunk
from generation.rag.validation import verify_citations
from scripts import eval_ragas_s11 as evaluation


def _sample():
    chunk = RetrievedChunk(
        id=1, content="Auth: 16 hours", budget_id="BUD-1",
        sector="finance", project_year=2024, chunk_type="budget_component",
    )
    estimate = Estimate(
        confidence="medium", reasoning="Partial scope supported.",
        modules=[{"name": "Auth", "description": "Access control", "tasks": [
            {"name": "Login", "description": "OAuth flow", "engineer_days": 2,
             "grounded": True, "sources": [
                 {"chunk_id": "1", "document_id": "BUD-1", "evidence": "16 hours"},
             ]},
            {"name": "Novel", "grounded": False, "engineer_days": None},
        ]}],
        assumptions=[{
            "description": "Novel scope unsupported", "impact": "high", "rationale": "No analog",
        }],
    )
    return evaluation.EvaluationSample(
        id="Q1", request_id="offline",
        question="Estimate auth", ground_truth="2 days",
        answer=evaluation.render_estimate_text(estimate), estimate=estimate,
        contexts=[chunk.content], kept_chunks=[chunk], context_block=build_context_block([chunk]),
        citation_report=verify_citations(estimate, {"1"}),
        structured_query={"function": "auth"}, search_text="auth",
    )


def test_render_keeps_every_claim_and_null_effort():
    estimate = _sample().estimate
    assert json.loads(evaluation.render_estimate_text(estimate)) == estimate.model_dump()


@pytest.mark.parametrize("field", ["contexts", "context_block", "answer", "citation_report"])
def test_sample_rejects_context_or_claim_drift(field):
    body = _sample().model_dump()
    body[field] = {
        "contexts": ["Not given to the generator"], "context_block": "different block",
        "answer": "Only the good claims", "citation_report": {
            **body["citation_report"], "insufficient_lines": 0,
        },
    }[field]
    with pytest.raises(ValidationError):
        evaluation.EvaluationSample.model_validate(body)


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_metric_is_not_a_zero_or_a_partial_average(invalid):
    rows = [{metric: 0.5 for metric in evaluation.METRIC_NAMES} for _ in range(5)]
    rows[2]["faithfulness"] = invalid
    with pytest.raises(ValueError, match="Q3"):
        evaluation.markdown_table(rows)


def test_table_contains_five_queries_and_arithmetic_average():
    rows = [{metric: index / 4 for metric in evaluation.METRIC_NAMES} for index in range(5)]
    table, average = evaluation.markdown_table(rows)
    assert len(table.splitlines()) == 8
    assert all(f"| Q{index} |" in table for index in range(1, 6))
    assert all(value == 0.5 for value in average.values())
    with pytest.raises(ValueError, match="five"):
        evaluation.markdown_table(rows[:4])


def test_missing_metric_is_rejected():
    rows = [{metric: 0.5 for metric in evaluation.METRIC_NAMES} for _ in range(5)]
    del rows[0]["context_recall"]
    with pytest.raises(ValueError, match="context_recall"):
        evaluation.markdown_table(rows)


@pytest.mark.parametrize("ids", [
    ["Q1", "Q2", "Q3", "Q4"], ["Q1", "Q2", "Q3", "Q4", "Q4"],
])
def test_scoring_rejects_partial_or_duplicate_queries(tmp_path, ids):
    path = tmp_path / "samples.json"
    evaluation.write_json(path, {
        "complete": True, "samples": [
            {**_sample().model_dump(mode="json"), "id": qid} for qid in ids
        ],
    })
    with pytest.raises(ValueError, match="exactly Q1-Q5"):
        evaluation.load_samples(path)


@pytest.mark.parametrize("no_context", [False, True])
async def test_collection_passes_and_records_only_kept_context(monkeypatch, no_context):
    import dependencies
    from generation.rag import estimator, query_reformulator
    from generation.rag.retrieval import search_pipeline

    sample = _sample()
    first = sample.kept_chunks[0]
    second = first.model_copy(update={"id": 2, "content": "Dropped evidence"})
    settings = SimpleNamespace(
        RETRIEVAL_TOP_K=10, RETRIEVAL_RECALL_TOP_K=50, RERANK_TOP_N=5, RRF_K=60,
        MAX_CONTEXT_TOKENS=0 if no_context else len(build_context_block([first])),
    )
    monkeypatch.setattr("config.get_settings", lambda: settings)
    monkeypatch.setattr(
        dependencies, "get_token_encoder", lambda: SimpleNamespace(encode=list),
    )

    async def reformulate(_text):
        return EstimationQuery(function="auth")

    async def retrieve(**kwargs):
        assert kwargs["chunk_types"] == ["budget_component"]
        return RetrievalResult(
            chunks=[first, second], low_confidence=False, candidates_evaluated=2,
        )

    async def generate(context, structured_query):
        assert context == build_context_block([first])
        return sample.estimate

    monkeypatch.setattr(query_reformulator, "reformulate_query", reformulate)
    monkeypatch.setattr(search_pipeline, "retrieve", retrieve)
    monkeypatch.setattr(estimator, "generate_estimate", generate)
    with structlog.contextvars.bound_contextvars(request_id="eval-offline"):
        if no_context:
            with pytest.raises(RuntimeError, match="no usable context"):
                await evaluation.collect_sample(
                    {"id": "Q1", "query": "auth", "transcript": "auth brief",
                     "ground_truth": "2 days"},
                    SimpleNamespace(embed_one=lambda _text: [0.0]),
                )
            return
        result = await evaluation.collect_sample(
            {"id": "Q1", "query": "auth", "transcript": "auth brief", "ground_truth": "2 days"},
            SimpleNamespace(embed_one=lambda _text: [0.0]),
        )
    assert result.contexts == [first.content]
    assert result.kept_chunks == [first]
    assert result.request_id == "eval-offline"


@pytest.mark.parametrize("non_finite", [False, True])
def test_scorer_persists_only_complete_numeric_results(tmp_path, monkeypatch, non_finite):
    import pandas as pd

    sample = _sample()
    samples = [sample.model_copy(update={"id": qid}) for qid in evaluation.QUERY_IDS]
    monkeypatch.setattr(evaluation, "load_samples", lambda path: ({
        "judge_model": "judge", "embedding_model": "embeddings",
        "golden_sha256": "offline", "configuration": {"search_mode": "hybrid"},
    }, samples))
    monkeypatch.setattr("config.get_settings", lambda: SimpleNamespace(OPENAI_API_KEY="test"))
    monkeypatch.setattr(evaluation, "version", lambda name: "offline-test")
    calls = []

    def evaluate(dataset, **kwargs):
        calls.append(kwargs)
        assert len(dataset) == 5
        assert set(dataset[0]) == {"question", "answer", "contexts", "ground_truth"}
        assert kwargs["raise_exceptions"] is True
        rows = [{metric: 0.5 for metric in evaluation.METRIC_NAMES} for _ in range(5)]
        if non_finite:
            rows[3]["context_recall"] = float("nan")
        return SimpleNamespace(to_pandas=lambda: pd.DataFrame(rows))

    monkeypatch.setattr(evaluation, "ragas_dependencies", lambda: (
        SimpleNamespace(from_list=lambda rows: rows),
        lambda **kwargs: kwargs, lambda **kwargs: kwargs, evaluate,
        lambda client: client, lambda client: client, list(evaluation.METRIC_NAMES),
    ))
    source, output = tmp_path / "samples.json", tmp_path / "scores.json"
    source.write_text("{}", encoding="utf-8")
    if non_finite:
        with pytest.raises(ValueError, match="Q4"):
            evaluation.score_samples(source, output)
        assert not output.exists()
        assert not output.with_suffix(".md").exists()
    else:
        evaluation.score_samples(source, output)
        report = json.loads(output.read_text())
        assert all(value == 0.5 for value in report["average"].values())
        assert len(report["per_query"]) == 5
        assert output.with_suffix(".md").read_text().count("| Q") == 5
        with pytest.raises(FileExistsError):
            evaluation.score_samples(source, output)
    assert len(calls) == 1
