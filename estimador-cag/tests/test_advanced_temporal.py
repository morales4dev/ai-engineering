from datetime import date

from generation.rag.retrieval.temporal import apply_temporal_decay, decay_weight
from generation.rag.schemas import RetrievedChunk


def _chunk(chunk_id: int, dated: date | None) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id,
        content=str(chunk_id),
        sector="unknown",
        project_year=0,
        chunk_type="doc_section",
        distance=0.2,
        document_date=dated,
    )


def test_decay_is_soft_and_recent_chunks_can_overtake_old_results():
    today = date(2025, 1, 1)
    old = _chunk(1, date(2020, 1, 1))
    recent = _chunk(2, date(2024, 12, 1))
    result = apply_temporal_decay(
        [(old, 1.0), (recent, 0.9)],
        half_life_days=365,
        reference_date=today,
    )
    assert result[0][0].id == 2
    assert decay_weight(365, 365) == 0.5
