"""When to compress, what to compress, and what to keep verbatim.

The policy is the only mutator of ``ConversationHistory`` beyond ``append``.
After each turn: peel oldest pairs while over the cap; promote anchors;
fold the rest into the cumulative summary.
"""

from __future__ import annotations

import structlog

from sessions.compression.anchors import AnchorDetector
from sessions.compression.summarizer import CumulativeSummarizer
from sessions.models import ConversationHistory, Message

log = structlog.get_logger()


class CompressionPolicy:
    def __init__(
        self,
        *,
        anchor_detector: AnchorDetector,
        summarizer: CumulativeSummarizer,
    ) -> None:
        self.anchor_detector = anchor_detector
        self.summarizer = summarizer

    def should_compress(self, history: ConversationHistory) -> bool:
        return len(history.messages) > history.max_turns * 2

    def apply(self, history: ConversationHistory) -> None:
        """Mutate ``history`` in place. No-op when the window is under the cap."""
        if not self.should_compress(history):
            return

        evicted_for_summary: list[Message] = []
        promoted_anchor_rules: list[list[str]] = []

        while len(history.messages) > history.max_turns * 2:
            if len(history.messages) < 2:
                break
            user_msg = history.messages[0]
            assistant_msg = history.messages[1]

            match = self.anchor_detector.detect(user_msg)
            if match.is_anchor:
                history.anchors.append(user_msg)
                history.anchors.append(assistant_msg)
                promoted_anchor_rules.append(match.matched_rules)
            else:
                evicted_for_summary.append(user_msg)
                evicted_for_summary.append(assistant_msg)

            del history.messages[:2]

        if evicted_for_summary:
            history.summary = self.summarizer.summarize(
                previous_summary=history.summary,
                evicted=evicted_for_summary,
            )

        log.info(
            "history_compressed",
            promoted_anchors=len(promoted_anchor_rules),
            anchor_rules=[rule for rules in promoted_anchor_rules for rule in rules],
            evicted_to_summary=len(evicted_for_summary),
            summary_chars=len(history.summary or ""),
            anchors_count=len(history.anchors),
            recent_messages=len(history.messages),
        )


def apply_compression(
    history: ConversationHistory,
    *,
    llm_wrapper,
    compression_model: str,
    anchor_detection_mode: str = "heuristic",
) -> None:
    """Build detector + summarizer and run the policy once."""
    detector = AnchorDetector(
        mode=anchor_detection_mode,  # type: ignore[arg-type]
        llm_wrapper=llm_wrapper,
        llm_model=compression_model,
    )
    summarizer = CumulativeSummarizer(llm_wrapper=llm_wrapper, model=compression_model)
    policy = CompressionPolicy(anchor_detector=detector, summarizer=summarizer)
    policy.apply(history)
