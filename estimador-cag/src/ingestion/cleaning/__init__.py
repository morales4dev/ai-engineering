"""NOT ON THE HTTP PATH.

What:        Pandas cleaning + Pandera validation for budget records.
What for:    Repair disguised nulls, coerce types, dedup, then partition valid/quarantine/discard.
Why not wired: POST /api/v1/ingestion/runs only does catalog → load → parse → job row.
When useful: PYTHONPATH=src:. uv run python scripts/demo_cleaning_s06.py
"""
from ingestion.cleaning.budget_records import clean_budget_records
from ingestion.cleaning.policy import ValidationResult, validate_with_policy
from ingestion.cleaning.schemas import BudgetRecord

__all__ = [
    "BudgetRecord",
    "ValidationResult",
    "clean_budget_records",
    "validate_with_policy",
]
