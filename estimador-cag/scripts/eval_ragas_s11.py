#!/usr/bin/env python3
"""Collect grounded estimates once, then score saved samples with RAGAS."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from pydantic import BaseModel, Field, model_validator  # noqa: E402

from generation.rag.context_assembler import (  # noqa: E402
    build_context_block,
    truncate_to_token_budget,
)
from generation.rag.schemas import (  # noqa: E402
    CitationReport,
    Estimate,
    HallucinationReport,
    RetrievedChunk,
)
from generation.rag.validation import verify_citations  # noqa: E402

GOLDEN_PATH = ROOT / "evals/golden_generation_s11.json"
METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
QUERY_IDS = ["Q1", "Q2", "Q3", "Q4", "Q5"]
GENERATION_THRESHOLD = 1.2


class EvaluationSample(BaseModel):
    """Persist both RAGAS inputs and the exact context used to generate them."""

    id: str
    request_id: str
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    contexts: list[str] = Field(min_length=1)
    ground_truth: str = Field(min_length=1)
    estimate: Estimate
    kept_chunks: list[RetrievedChunk] = Field(min_length=1)
    context_block: str = Field(min_length=1)
    citation_report: CitationReport
    hallucination_report: HallucinationReport | None = None
    structured_query: dict
    search_text: str

    @model_validator(mode="after")
    def _traceability(self) -> EvaluationSample:
        if self.contexts != [chunk.content for chunk in self.kept_chunks]:
            raise ValueError(f"{self.id}: contexts do not match the retained chunks.")
        if self.context_block != build_context_block(self.kept_chunks):
            raise ValueError(f"{self.id}: assembled context does not match the retained chunks.")
        report = verify_citations(self.estimate, {str(chunk.id) for chunk in self.kept_chunks})
        if self.citation_report != report:
            raise ValueError(f"{self.id}: saved citation report does not match the estimate.")
        if self.answer != render_estimate_text(self.estimate):
            raise ValueError(f"{self.id}: answer omits or changes generated claims.")
        return self


def render_estimate_text(estimate: Estimate) -> str:
    """Keep every generated claim, including descriptions, evidence and assumptions."""
    return estimate.model_dump_json(indent=2)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
    )


async def collect_sample(
    item: dict, embedder, *, augment: bool = False, gate: bool = False,
) -> EvaluationSample:
    from config import get_settings
    from dependencies import get_token_encoder
    from generation.rag.estimator import generate_estimate
    from generation.rag.quality import augment_chunks, gate_estimate
    from generation.rag.query_reformulator import compose_search_text, reformulate_query
    from generation.rag.retrieval.search_pipeline import retrieve

    settings = get_settings()
    query = await reformulate_query(item["transcript"])
    search_text = compose_search_text(query)
    embedding = await asyncio.to_thread(embedder.embed_one, search_text)
    retrieval = await retrieve(
        query_embedding=embedding, query_text=search_text,
        search_mode="hybrid", rerank=True,
        top_k=settings.RETRIEVAL_TOP_K, recall_k=settings.RETRIEVAL_RECALL_TOP_K,
        rerank_top_n=settings.RERANK_TOP_N, distance_threshold=GENERATION_THRESHOLD,
        rrf_k=settings.RRF_K, chunk_types=["budget_component"],
    )
    kept = truncate_to_token_budget(
        retrieval.chunks, settings.MAX_CONTEXT_TOKENS, get_token_encoder(),
    )
    if not kept:
        raise RuntimeError(f"{item['id']}: no usable context; collection is incomplete.")
    if augment:
        kept = augment_chunks(kept)
    context = build_context_block(kept)
    estimate = await generate_estimate(context, structured_query=query)
    report = verify_citations(estimate, {str(chunk.id) for chunk in kept})
    semantic = None
    if gate:
        semantic = await gate_estimate(
            estimate, kept, tolerance=settings.HALLUCINATION_NUMERIC_TOLERANCE,
            model=settings.HALLUCINATION_JUDGE_MODEL,
        )
        if estimate.confidence in ("high", "medium") and any(
            line.status in ("degraded", "unverified") for line in semantic.lines
        ):
            estimate = estimate.model_copy(update={"confidence": "low"})
    import structlog

    request_id = structlog.contextvars.get_contextvars()["request_id"]
    logger = structlog.get_logger()
    logger.info("citation_report", request_id=request_id, phase="evaluation", **report.model_dump())
    if report.has_dangling:
        logger.warning(
            "evaluation_dangling_citations", request_id=request_id,
            query_id=item["id"], dangling_citations=report.dangling_citations,
        )
    return EvaluationSample(
        id=item["id"], request_id=request_id, question=item["query"],
        answer=render_estimate_text(estimate), contexts=[chunk.content for chunk in kept],
        ground_truth=item["ground_truth"], estimate=estimate, kept_chunks=kept,
        context_block=context, citation_report=report,
        hallucination_report=semantic,
        structured_query=query.model_dump(), search_text=search_text,
    )


async def collect_samples(path: Path, *, augment: bool = False, gate: bool = False) -> None:
    import structlog

    from config import get_settings
    from scripts.s08.s08_common import require_async_session_factory, require_embedder

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if [item["id"] for item in golden["queries"]] != QUERY_IDS:
        raise ValueError("The generation golden set must contain Q1-Q5, exactly once and in order.")
    retrieval_golden = json.loads((ROOT / "evals/golden_retrieval.json").read_text())
    for item, original in zip(golden["queries"], retrieval_golden["queries"][:5], strict=True):
        if (item["id"], item["query"]) != (original["id"], original["query"]):
            raise ValueError("Generation queries must match the retrieval golden set.")
    # Reserve the file before any paid call; never overwrite a previous collection.
    with path.open("x", encoding="utf-8") as handle:
        handle.write('{"complete": false, "samples": []}\n')
    settings = get_settings()
    require_async_session_factory()
    embedder = require_embedder()
    payload = {
        "complete": False,
        "created_at": datetime.now(UTC).isoformat(),
        "golden_sha256": hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest(),
        "judge_model": golden["judge_model"],
        "embedding_model": golden["embedding_model"],
        "configuration": {
            "reformulation_model": settings.REFORMULATION_MODEL,
            "generation_model": settings.GENERATION_MODEL,
            "generation_api": "openai_responses",
            "generation_client": "litellm.responses",
            "generation_reasoning_effort": settings.GENERATION_REASONING_EFFORT,
            "generation_max_tokens": settings.GENERATION_MAX_TOKENS,
            "retrieval_embedding_model": settings.EMBEDDING_MODEL,
            "search_mode": "hybrid", "rerank": True,
            "reranker_model": settings.RERANKER_MODEL,
            "distance_threshold": GENERATION_THRESHOLD,
            "top_k": settings.RETRIEVAL_TOP_K, "recall_k": settings.RETRIEVAL_RECALL_TOP_K,
            "rerank_top_n": settings.RERANK_TOP_N, "rrf_k": settings.RRF_K,
            "max_context_tokens": settings.MAX_CONTEXT_TOKENS,
            "chunk_types": ["budget_component"],
            "citation_policy": "single generation, audit only; no HTTP repair loop",
            "augmentation_enabled": augment, "hallucination_gate_enabled": gate,
        },
        "samples": [],
    }
    write_json(path, payload)
    for item in golden["queries"]:
        print(f"Collecting {item['id']} (paid reformulation, embedding and generation)...", flush=True)
        with structlog.contextvars.bound_contextvars(request_id=str(uuid4())):
            sample = await collect_sample(item, embedder, augment=augment, gate=gate)
        payload["samples"].append(sample.model_dump(mode="json"))
        write_json(path, payload)
    payload["complete"] = True
    write_json(path, payload)
    print(f"Saved all five samples to {path}. No RAGAS scoring has run.")


def load_samples(path: Path) -> tuple[dict, list[EvaluationSample]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("complete"):
        raise ValueError("Collection is incomplete. Do not score it as a five-query baseline.")
    samples = [EvaluationSample.model_validate(row) for row in payload["samples"]]
    if [sample.id for sample in samples] != QUERY_IDS:
        raise ValueError("Expected exactly Q1-Q5, without duplicates and in order.")
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if payload["golden_sha256"] != hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest():
        raise ValueError("Golden set changed since collection; keep the original version.")
    for sample, item in zip(samples, golden["queries"], strict=True):
        if (sample.question, sample.ground_truth) != (item["query"], item["ground_truth"]):
            raise ValueError(f"{sample.id}: question or reference differs from the golden set.")
    return payload, samples


def ragas_dependencies():
    """Import the real evaluation stack without constructing clients or calling APIs."""
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"
    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

    return (
        Dataset, ChatOpenAI, OpenAIEmbeddings, evaluate, LangchainEmbeddingsWrapper,
        LangchainLLMWrapper, [Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()],
    )


def check_dependencies() -> None:
    ragas_dependencies()
    for package in ("ragas", "datasets", "langchain-openai", "langchain-community"):
        print(f"{package}: {version(package)}")
    print("PASS: real RAGAS imports and four metrics are available; no model calls made.")


def validate_scores(rows: list[dict[str, float]]) -> None:
    if len(rows) != 5:
        raise ValueError("A baseline requires five scored queries.")
    for qid, row in zip(QUERY_IDS, rows, strict=True):
        for metric in METRIC_NAMES:
            value = row.get(metric)
            if value is None or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{qid}: missing, non-finite or out-of-range {metric}: {value!r}.")


def markdown_table(rows: list[dict[str, float]]) -> tuple[str, dict[str, float]]:
    validate_scores(rows)
    average = {metric: sum(row[metric] for row in rows) / 5 for metric in METRIC_NAMES}
    lines = [
        "| query | " + " | ".join(METRIC_NAMES) + " |",
        "| --- | " + " | ".join("---:" for _ in METRIC_NAMES) + " |",
    ]
    for qid, row in [*zip(QUERY_IDS, rows, strict=True), ("**average**", average)]:
        lines.append(f"| {qid} | " + " | ".join(f"{row[m]:.3f}" for m in METRIC_NAMES) + " |")
    return "\n".join(lines), average


def score_samples(source: Path, out: Path) -> None:
    payload, samples = load_samples(source)
    if out.suffix.lower() != ".json":
        raise ValueError("--out must end in .json; Markdown is written alongside it.")
    markdown_path = out.with_suffix(".md")
    if (
        source.resolve() in {out.resolve(), markdown_path.resolve()}
        or out.exists() or markdown_path.exists()
    ):
        raise FileExistsError("Choose new JSON/Markdown output paths; existing evidence is preserved.")
    (
        Dataset, ChatOpenAI, OpenAIEmbeddings, evaluate,
        LangchainEmbeddingsWrapper, LangchainLLMWrapper, metrics,
    ) = ragas_dependencies()
    from config import get_settings

    key = get_settings().OPENAI_API_KEY
    if not key:
        raise ValueError("Configure OPENAI_API_KEY in the process environment or project .env.")
    judge_model = payload["judge_model"]
    embedding_model = payload["embedding_model"]
    dataset = Dataset.from_list([
        {name: getattr(sample, name) for name in ("question", "answer", "contexts", "ground_truth")}
        for sample in samples
    ])
    print(f"Scoring Q1-Q5 with {judge_model} and {embedding_model} (paid calls)...", flush=True)
    result = evaluate(
        dataset, metrics=metrics,
        llm=LangchainLLMWrapper(ChatOpenAI(model=judge_model, temperature=0, api_key=key)),
        embeddings=LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(model=embedding_model, api_key=key),
        ),
        raise_exceptions=True,
    )
    frame = result.to_pandas()
    if len(frame) != 5 or any(metric not in frame.columns for metric in METRIC_NAMES):
        raise ValueError("RAGAS did not return five rows with all four metrics.")
    rows = [
        {metric: float(frame.iloc[index][metric]) for metric in METRIC_NAMES}
        for index in range(5)
    ]
    table, average = markdown_table(rows)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "samples_file": str(source), "samples_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "golden_sha256": payload["golden_sha256"],
        "judge_model": judge_model, "embedding_model": embedding_model,
        "versions": {name: version(name) for name in ("ragas", "datasets", "langchain-openai")},
        "configuration": payload["configuration"],
        "per_query": [
            {"id": sample.id, **row, "citation_report": sample.citation_report.model_dump()}
            for sample, row in zip(samples, rows, strict=True)
        ],
        "average": average, "table_markdown": table,
    }
    write_json(out, report)
    markdown_path.write_text(table + "\n", encoding="utf-8")
    print(table)
    print(f"Saved {out} and {markdown_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--collect-only", type=Path, metavar="PATH")
    mode.add_argument("--score-file", type=Path, metavar="PATH")
    mode.add_argument("--inspect-samples", type=Path, metavar="PATH")
    mode.add_argument("--check-deps", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "evals/ragas_baseline_s11.json")
    parser.add_argument("--augment", action="store_true", help="Apply context augmentation.")
    parser.add_argument("--gate", action="store_true", help="Run the paid semantic judge.")
    args = parser.parse_args()
    if args.check_deps:
        check_dependencies()
    elif args.inspect_samples:
        _, samples = load_samples(args.inspect_samples)
        for sample in samples:
            report = sample.citation_report
            print(
                f"{sample.id}: contexts={len(sample.contexts)}, grounded={report.grounded_lines}, "
                f"dangling={report.dangling_citations}, insufficient={report.insufficient_lines}, "
                f"request_id={sample.request_id}",
            )
        print("PASS: five complete, traceable samples. Inspect their content before scoring.")
    elif args.collect_only:
        asyncio.run(collect_samples(args.collect_only, augment=args.augment, gate=args.gate))
    else:
        score_samples(args.score_file, args.out)


if __name__ == "__main__":
    main()
