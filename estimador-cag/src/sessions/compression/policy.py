"""Window-only peel of overflow pairs after ``append``.

``CompressionPolicy`` is the only mutator of ``ConversationHistory`` beyond
``append``. This step drops the oldest user/assistant pair while the
sliding window is over ``max_turns * 2``. Anchors and cumulative summary
are out of this step.
"""

from __future__ import annotations

import structlog

from sessions.models import ConversationHistory

log = structlog.get_logger()


class CompressionPolicy:
    def should_compress(self, history: ConversationHistory) -> bool:
        return len(history.messages) > history.max_turns * 2

    def apply(self, history: ConversationHistory) -> None:
        """Mutate ``history`` in place: drop oldest pairs until the window fits."""
        if not self.should_compress(history):
            return

        evicted = 0
        while len(history.messages) > history.max_turns * 2:
            if len(history.messages) < 2:
                break
            del history.messages[:2]
            evicted += 2

        log.info(
            "history_window_trimmed",
            evicted_messages=evicted,
            recent_messages=len(history.messages),
            max_turns=history.max_turns,
        )


def apply_compression(history: ConversationHistory) -> None:
    """Run the window policy once. No LLM args yet."""
    CompressionPolicy().apply(history)
