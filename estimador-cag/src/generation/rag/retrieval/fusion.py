"""Reciprocal Rank Fusion for combining independent retrieval rankings."""

from itertools import zip_longest

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[int]],
    *,
    k: int = DEFAULT_RRF_K,
) -> list[tuple[int, float]]:
    """Fuse rankings by position; duplicate ids count only at their first rank."""
    if k <= 0:
        raise ValueError("RRF smoothing constant k must be positive")

    scores: dict[int, float] = {}
    for ranking in rankings:
        seen: set[int] = set()
        for position, chunk_id in enumerate(ranking):
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def round_robin_merge(ranked_lists: list[list], *, key=lambda item: item) -> list:
    """Interleave rankings by position, keeping the first instance of each key."""
    seen: set = set()
    merged: list = []
    for column in zip_longest(*ranked_lists):
        for item in column:
            if item is None:
                continue
            identity = key(item)
            if identity not in seen:
                seen.add(identity)
                merged.append(item)
    return merged
