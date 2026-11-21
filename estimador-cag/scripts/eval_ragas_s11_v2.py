#!/usr/bin/env python3
"""V2: score RAGAS against a reduced JSON projection of the estimate.

V1 sends the full ``Estimate`` JSON (sources, chunk ids, verbatim evidence) as the
RAGAS ``answer``; at 15-31K chars faithfulness exceeds RAGAS's 180 s per-job timeout
and evidence copied from the context inflates the score. V2 reads the same V1 samples
and projects each estimate in memory onto ``EvalAnswer``: JSON with only the claims
the estimate makes. Citations stay audited by ``verify_citations``. The report keeps
the projection name, its schema and every ``ragas_answer`` the judge received.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from eval_ragas_s11 import (
    METRIC_NAMES,
    ROOT,
    check_dependencies,
    load_samples,
    markdown_table,
    ragas_dependencies,
    write_json,
)
from pydantic import BaseModel

from generation.rag.schemas import Confidence, Estimate

ANSWER_FORMAT_NAME = "eval_answer_json_v2"


class EvalTask(BaseModel):
    name: str
    engineer_days: int | None
    grounded: bool


class EvalModule(BaseModel):
    name: str
    tasks: list[EvalTask]


class EvalAnswer(BaseModel):
    """Claims of an estimate as judged by RAGAS; citations are audited separately."""

    total_engineer_days: int | None
    duration_weeks: int | None
    confidence: Confidence
    modules: list[EvalModule]
    assumptions: list[str]
    reasoning: str
    insufficient_context_explanation: str | None

    @classmethod
    def from_estimate(cls, estimate: Estimate) -> EvalAnswer:
        return cls(
            total_engineer_days=estimate.total_engineer_days,
            duration_weeks=estimate.duration_weeks,
            confidence=estimate.confidence,
            modules=[
                EvalModule(
                    name=module.name,
                    tasks=[
                        EvalTask(
                            name=task.name, engineer_days=task.engineer_days,
                            grounded=task.grounded,
                        )
                        for task in module.tasks
                    ],
                )
                for module in estimate.modules
            ],
            assumptions=[assumption.description for assumption in estimate.assumptions],
            reasoning=estimate.reasoning,
            insufficient_context_explanation=estimate.insufficient_context_explanation,
        )


def render_ragas_answer(estimate: Estimate) -> str:
    """Compact JSON: indentation only adds tokens for the judge."""
    answer = EvalAnswer.from_estimate(estimate).model_dump_json()
    if EvalAnswer.model_validate_json(answer) != EvalAnswer.from_estimate(estimate):
        raise ValueError("Projected answer does not round-trip to the estimate's claims.")
    return answer


def answer_format() -> dict:
    return {"name": ANSWER_FORMAT_NAME, "schema": EvalAnswer.model_json_schema()}


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
    from ragas import RunConfig  # noqa: F401  # used by the commented evaluate() variant

    from config import get_settings

    key = get_settings().OPENAI_API_KEY
    if not key:
        raise ValueError("Configure OPENAI_API_KEY in the process environment or project .env.")
    judge_model = payload["judge_model"]
    embedding_model = payload["embedding_model"]
    ragas_answers = [render_ragas_answer(sample.estimate) for sample in samples]
    dataset = Dataset.from_list([
        {
            "question": sample.question, "answer": ragas_answer,
            "contexts": sample.contexts, "ground_truth": sample.ground_truth,
        }
        for sample, ragas_answer in zip(samples, ragas_answers, strict=True)
    ])
    judge = LangchainLLMWrapper(ChatOpenAI(model=judge_model, temperature=0, api_key=key))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=embedding_model, api_key=key))
    print(f"Scoring Q1-Q5 with {judge_model} and {embedding_model} (paid calls)...", flush=True)
    result = evaluate(dataset, metrics=metrics, llm=judge, embeddings=embeddings, raise_exceptions=True)
    # result = evaluate(dataset, metrics=metrics, llm=judge, embeddings=embeddings, raise_exceptions=True, run_config=RunConfig(timeout=300, max_workers=4, max_retries=3))
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
        "answer_format": answer_format(),
        "golden_sha256": payload["golden_sha256"],
        "judge_model": judge_model, "embedding_model": embedding_model,
        "versions": {name: version(name) for name in ("ragas", "datasets", "langchain-openai")},
        "configuration": payload["configuration"],
        "per_query": [
            {
                "id": sample.id, **row, "ragas_answer": ragas_answer,
                "citation_report": sample.citation_report.model_dump(),
            }
            for sample, row, ragas_answer in zip(samples, rows, ragas_answers, strict=True)
        ],
        "average": average, "table_markdown": table,
    }
    write_json(out, report)
    markdown_path.write_text(table + "\n", encoding="utf-8")
    print(table)
    print(f"Saved {out} and {markdown_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--score-file", type=Path, metavar="SAMPLES")
    mode.add_argument("--inspect-samples", type=Path, metavar="SAMPLES")
    mode.add_argument("--check-deps", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "evals/ragas_baseline_s11_v2.json")
    args = parser.parse_args()
    if args.check_deps:
        check_dependencies()
    elif args.inspect_samples:
        _, samples = load_samples(args.inspect_samples)
        for sample in samples:
            print(
                f"{sample.id}: answer {len(sample.answer)} -> "
                f"{len(render_ragas_answer(sample.estimate))} chars, contexts={len(sample.contexts)}",
            )
        print("PASS: five traceable samples; projection computed, no model calls made.")
    else:
        score_samples(args.score_file, args.out)


if __name__ == "__main__":
    main()
