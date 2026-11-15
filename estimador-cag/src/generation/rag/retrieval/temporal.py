"""Soft temporal re-ranking applied after retrieval and optional cross-encoding."""

from __future__ import annotations

from datetime import date

from generation.rag.schemas import RetrievedChunk


def decay_weight(age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0 or age_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def apply_temporal_decay(
    scored_chunks: list[tuple[RetrievedChunk, float]],
    *,
    half_life_days: float,
    reference_date: date,
) -> list[tuple[RetrievedChunk, float]]:
    weighted = []
    for chunk, score in scored_chunks:
        age_days = (
            (reference_date - chunk.document_date).days
            if chunk.document_date is not None
            else 0
        )
        weighted.append((chunk, score * decay_weight(age_days, half_life_days)))
    return sorted(weighted, key=lambda pair: pair[1], reverse=True)
