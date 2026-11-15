from __future__ import annotations

import pytest

from generation.rag.retrieval.fusion import reciprocal_rank_fusion


def test_fusion_rewards_items_found_by_both_retrievers():
    fused = reciprocal_rank_fusion([[1, 2], [2, 3]])

    assert fused[0][0] == 2
    assert {chunk_id for chunk_id, _score in fused} == {1, 2, 3}


def test_fusion_is_deterministic_and_ignores_duplicate_ids():
    assert reciprocal_rank_fusion([[7, 8, 7]], k=60) == reciprocal_rank_fusion([[7, 8]], k=60)
    assert reciprocal_rank_fusion([[10, 20], [20, 10]])[0][0] == 10


def test_fusion_rejects_non_positive_smoothing_constant():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[1]], k=0)
