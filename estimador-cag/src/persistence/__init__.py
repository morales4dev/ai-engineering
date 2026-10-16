"""Persistence layer for history + Session 6 ingestion.

Holds the declarative ``Base`` and row models. The engine is lazy — importing
this package does not connect. Repositories live in ``persistence.repositories``.
"""
from persistence.models import (
    Base,
    EstimationRow,
    IngestionJobRow,
    PseudonymMappingRow,
)

__all__ = [
    "Base",
    "EstimationRow",
    "IngestionJobRow",
    "PseudonymMappingRow",
]
