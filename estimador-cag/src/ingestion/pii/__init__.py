"""NOT ON THE HTTP PATH.

What:        Presidio Spanish analyzer + consistent HMAC-backed pseudonymizer.
What for:    Replace PII (and BUDGET_ID / CLIENT_CODE) with stable fake values.
Why not wired: POST /api/v1/ingestion/runs only does catalog → load → parse → job row.
When useful: PYTHONPATH=src:. uv run python scripts/demo_pii_s06.py
"""
from ingestion.pii.analyzer import build_analyzer
from ingestion.pii.mapping_store import (
    InMemoryMappingStore,
    MappingStore,
    PostgresMappingStore,
)
from ingestion.pii.pseudonymizer import (
    ConsistentPseudonymizer,
    PseudonymizationResult,
)
from ingestion.pii.recognizers import (
    BudgetIdRecognizer,
    ClientCodeRecognizer,
)

__all__ = [
    "BudgetIdRecognizer",
    "ClientCodeRecognizer",
    "ConsistentPseudonymizer",
    "InMemoryMappingStore",
    "MappingStore",
    "PostgresMappingStore",
    "PseudonymizationResult",
    "build_analyzer",
]
