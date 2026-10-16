#!/usr/bin/env python3
"""NOT ON THE HTTP PATH.

What:        Host demo of ConsistentPseudonymizer over a seed transcript.
What for:    Show Spanish Presidio + custom recognizers replacing PII consistently.
Why not wired: POST /api/v1/ingestion/runs only does catalog → load → parse → job row.
When useful: PYTHONPATH=src:. uv run python scripts/demo_pii_s06.py

Needs es_core_news_md on the host (step 6 downloads it). Uses InMemoryMappingStore,
not Postgres. Does not call FastAPI or ingest_source.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # estimador-cag/
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# A salt is required to build the pseudonymizer; use a demo one if unset.
os.environ.setdefault("PSEUDONYM_HASH_SALT", "demo-salt")

from ingestion.pii import (  # noqa: E402
    ConsistentPseudonymizer,
    InMemoryMappingStore,
    build_analyzer,
)

TRANSCRIPT = ROOT / "data" / "seed" / "transcripts" / "transcripcion_2025-02-03_betanorte.txt"


def main() -> int:
    if not TRANSCRIPT.exists():
        print(f"ERROR: no existe {TRANSCRIPT}")
        return 1

    pseudo = ConsistentPseudonymizer(
        analyzer=build_analyzer(),  # es_core_news_md + BUDGET_ID/CLIENT_CODE recognizers
        mapping_store=InMemoryMappingStore(),
        salt=os.environ["PSEUDONYM_HASH_SALT"],
    )
    result = pseudo.pseudonymize(TRANSCRIPT.read_text(encoding="utf-8"))

    print(f"Transcripción: {TRANSCRIPT.name}")
    print("\n--- Texto pseudonimizado (primeros 400 chars) ---")
    print(result.pseudonymized_text[:400])

    print(f"\n--- Mappings aplicados ({len(result.applied)}) ---")
    for m in result.applied[:12]:
        print(f"  {m.entity_type:14} → {m.pseudonym}")
    print("\nMismo valor original → mismo pseudónimo en todo el documento "
          "(consistencia por valor, no por chunk).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
