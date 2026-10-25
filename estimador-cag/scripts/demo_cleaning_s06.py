#!/usr/bin/env python3
"""NOT ON THE HTTP PATH.

What:        Host demo of clean_budget_records + validate_with_policy over data/seed/budgets.
What for:    Show the 6-file → 5-row → discard-negative-amount story without hitting the API.
Why not wired: POST /api/v1/ingestion/runs only does catalog → load → parse → job row.
When useful: PYTHONPATH=src:. uv run python scripts/demo_cleaning_s06.py

Teaching script, not an endpoint and not a test. Reads the 6 JSON files under
data/seed/budgets, runs cleaning then Pandera policy, prints the partition
report. Does not call FastAPI, does not write Postgres, does not enter
ingest_source. Same calls you would type in an interactive ``python`` prompt,
already sequenced so you can re-run the demo without retyping them.

Expected story:

* 6 ficheros entran, 5 llegan a validación (el dedup colapsa BUDGET-2024-0005).
* el ``total_amount: -50000`` se descarta; el resto pasa.
* The seed can also quarantine a row (BUDGET-2024-0002 when we last ran it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # estimador-cag/
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ingestion.cleaning import clean_budget_records, validate_with_policy  # noqa: E402

BUDGETS_DIR = ROOT / "data" / "seed" / "budgets"


def main() -> int:
    paths = sorted(BUDGETS_DIR.glob("*.json"))
    if not paths:
        print(f"ERROR: no budget JSON files under {BUDGETS_DIR}")
        return 1

    records = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    print(f"Ficheros leídos: {len(records)}  ({BUDGETS_DIR})")

    df = clean_budget_records(records)
    print(f"Filas tras limpieza + dedup: {len(df)}")

    result = validate_with_policy(df)
    print("\nReport:")
    for key, value in result.report.items():
        print(f"  {key}: {value}")

    if not result.discarded.empty:
        print("\nDescartadas:")
        print(result.discarded[["budget_id", "total_amount"]].to_string(index=False))
    if not result.quarantined.empty:
        print("\nEn cuarentena:")
        print(result.quarantined[["budget_id", "client_name"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
