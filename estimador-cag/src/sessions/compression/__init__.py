"""Hybrid memory compression for long conversations.

``CompressionPolicy`` peels overflow after ``append``: anchors stay
verbatim, the rest folds into a cumulative summary.
"""

from sessions.compression.anchors import AnchorDetector, AnchorMatch
from sessions.compression.policy import CompressionPolicy, apply_compression
from sessions.compression.summarizer import CumulativeSummarizer

__all__ = [
    "AnchorDetector",
    "AnchorMatch",
    "CompressionPolicy",
    "CumulativeSummarizer",
    "apply_compression",
]
