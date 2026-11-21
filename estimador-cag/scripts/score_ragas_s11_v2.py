#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#   "ragas==0.4.3",
#   "datasets>=2.19,<5",
#   "langchain-community>=0.3.27,<0.4",
#   "langchain-openai>=0.3.28,<0.4",
#   "pydantic-settings>=2,<3",
# ]
# ///
"""Isolated V2 scorer: reads the V1 samples, scores a reduced JSON projection of each
estimate; keeps RAGAS out of the application env.

Script lockfile (required by ``--locked``), either:
    uv lock --script scripts/score_ragas_s11_v2.py
    # or reuse V1's lock, the dependencies are identical:
    cp scripts/score_ragas_s11.py.lock scripts/score_ragas_s11_v2.py.lock

Run:
    uv run --locked --script scripts/score_ragas_s11_v2.py --check-deps
    uv run --locked --script scripts/score_ragas_s11_v2.py --score-file evals/ragas_samples_s11.json --out evals/ragas_baseline_s11_v2.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from eval_ragas_s11_v2 import ROOT, check_dependencies, score_samples


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--score-file", type=Path)
    mode.add_argument("--check-deps", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "evals/ragas_baseline_s11_v2.json")
    args = parser.parse_args()
    if args.check_deps:
        check_dependencies()
    else:
        score_samples(args.score_file, args.out)


if __name__ == "__main__":
    main()
