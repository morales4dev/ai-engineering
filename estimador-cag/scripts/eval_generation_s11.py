#!/usr/bin/env python3
"""Compare saved V2 RAGAS scores with the local baseline, or inspect a scored sample."""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.eval_ragas_s11 import METRIC_NAMES


def load_report(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if [row["id"] for row in report["per_query"]] != ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        raise ValueError("A report must contain Q1–Q5 in order.")
    for metric in METRIC_NAMES:
        value = report["average"][metric]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid average for {metric}.")
    return report


def regression_gate(report: dict, baseline: dict, tolerance: float = 0.05) -> bool:
    for key in ("golden_sha256", "judge_model", "embedding_model", "answer_format"):
        if report[key] != baseline[key]:
            raise ValueError(f"Reports have incompatible {key}; comparison would be misleading.")
    for key, value in baseline["configuration"].items():
        if key not in ("augmentation_enabled", "hallucination_gate_enabled") and (
            report["configuration"].get(key) != value
        ):
            raise ValueError(f"Reports have incompatible configuration: {key}.")
    passed = True
    for metric in METRIC_NAMES:
        floor = baseline["average"][metric] - tolerance
        ok = report["average"][metric] >= floor
        print(f"{metric}: {report['average'][metric]:.3f} (floor {floor:.3f}) {'PASS' if ok else 'FAIL'}")
        passed &= ok
    dangling = sum(len(row["citation_report"]["dangling_citations"]) for row in report["per_query"])
    print(f"Dangling citations: {dangling}")
    return passed and dangling == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--gate", type=Path, help="Compare a scored report with the baseline.")
    mode.add_argument("--monitor", type=Path, help="Inspect metrics in a saved scored report.")
    parser.add_argument("--baseline", type=Path, default=ROOT / "evals/ragas_baseline_s11.json")
    args = parser.parse_args()
    report = load_report(args.gate or args.monitor)
    if args.gate:
        passed = regression_gate(report, load_report(args.baseline))
        print("PASS" if passed else "FAIL")
        raise SystemExit(0 if passed else 1)
    print("Saved evaluation report (not a live traffic monitor):")
    for metric in ("faithfulness", "answer_relevancy"):
        print(f"{metric}: {report['average'][metric]:.3f}")


if __name__ == "__main__":
    main()
