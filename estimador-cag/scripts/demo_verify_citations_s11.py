#!/usr/bin/env python3
"""Deterministic citation demo: no keys, services, encoders or model downloads."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generation.rag.schemas import Estimate  # noqa: E402
from generation.rag.validation import verify_citations  # noqa: E402


def main() -> None:
    estimate = Estimate(
        confidence="low", reasoning="Deterministic demo; only chunk 1 was supplied.",
        modules=[{"name": "Demo", "tasks": [
            {"name": "Supported", "grounded": True, "engineer_days": 2, "sources": [
                {"chunk_id": "1", "document_id": "BUD-1", "evidence": "16 hours"},
            ]},
            {"name": "Invented citation", "grounded": True, "engineer_days": 3, "sources": [
                {"chunk_id": "invented", "document_id": "BUD-2", "evidence": "24 hours"},
            ]},
            {"name": "No source data", "grounded": False, "engineer_days": None},
        ]}],
    )
    report = verify_citations(estimate, {"1"})
    assert (report.grounded_lines, report.dangling_lines, report.insufficient_lines) == (1, 1, 1)
    assert report.dangling_citations == ["invented"]
    print(report.model_dump_json(indent=2))
    print("PASS: grounded=1, dangling=1, insufficient=1; invented citation detected.")


if __name__ == "__main__":
    main()
