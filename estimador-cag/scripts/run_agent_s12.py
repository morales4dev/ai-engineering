#!/usr/bin/env python3
"""Run the Session 12 agent and optionally save its trace."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dependencies import get_llm_wrapper
from generation.agentic.agent import run_agent
from generation.agentic.tools import SearchArgs, real_retrieval


def _stub_backend():
    path = ROOT / "exercises/session-12/reference_retrieval.py"
    spec = importlib.util.spec_from_file_location("session12_reference_retrieval", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load the retrieval stub: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async def search(args: SearchArgs) -> list[dict]:
        filters = args.filters
        if filters and (
            filters.project_year_min is not None or filters.project_year_max is not None
        ):
            raise ValueError("The stub does not support year filters; use null.")
        return module.search_budgets_stub(
            args.query,
            {"sectors": filters.sectors} if filters else None,
        )

    return search


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the manual estimation agent.")
    parser.add_argument("transcript", type=Path, help="Meeting transcript in a UTF-8 text file.")
    parser.add_argument("--model", default="gpt-5", help="OpenAI model (default: gpt-5).")
    parser.add_argument(
        "--effort",
        choices=["minimal", "low", "medium", "high"],
        default="medium",
        help="Reasoning effort (default: medium).",
    )
    parser.add_argument("--max-iterations", type=int, default=10, help="Maximum Responses turns.")
    parser.add_argument("--stub", action="store_true", help="Use fictional retrieval data.")
    parser.add_argument("--out", type=Path, help="Save the trace to a new file.")
    args = parser.parse_args()

    if args.max_iterations < 1:
        parser.error("--max-iterations must be at least one")
    if args.out and (args.out.exists() or not args.out.parent.is_dir()):
        parser.error("--out must be a new file in an existing directory")
    try:
        transcript = args.transcript.read_text(encoding="utf-8")
        result = asyncio.run(
            run_agent(
                transcript,
                wrapper=get_llm_wrapper(),
                model=args.model,
                reasoning_effort=args.effort,
                max_iterations=args.max_iterations,
                retrieval_backend=_stub_backend() if args.stub else real_retrieval,
            )
        )
        rendered = result.render()
        print(rendered)
        if args.out:
            with args.out.open("x", encoding="utf-8") as output:
                output.write(rendered + "\n")
            print(f"\nTrace saved to {args.out}")
        return 0 if result.status == "completed" else 1
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
