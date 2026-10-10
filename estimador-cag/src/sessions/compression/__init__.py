"""Window policy for conversational history.

``CompressionPolicy`` is the only mutator after ``append``. This step is
window-only: peel oldest user/assistant pairs until the sliding window
fits. Anchors and cumulative summary land in a later step.
"""

from sessions.compression.policy import CompressionPolicy, apply_compression

__all__ = [
    "CompressionPolicy",
    "apply_compression",
]
