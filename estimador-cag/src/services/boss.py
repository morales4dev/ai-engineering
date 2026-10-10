"""Boss orchestrator — coordinates Actor and Critic.

The Boss does not do LLM calls of its own. It only chooses what to do next.
"""

from __future__ import annotations

from typing import Callable

import structlog

from schemas.acb import ACBIteration, BossDecision, BossTrace
from schemas.critic import CriticFeedback
from schemas.estimation import EstimationResult

log = structlog.get_logger()


ActorCallable = Callable[[CriticFeedback | None], EstimationResult]
CriticCallable = Callable[[EstimationResult], CriticFeedback]


class Boss:
    """Stateless orchestrator. One ``run`` per estimation."""

    def __init__(self, *, max_iterations: int = 2) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        self.max_iterations = max_iterations

    def run(
        self,
        *,
        actor: ActorCallable,
        critic: CriticCallable,
    ) -> tuple[EstimationResult, BossTrace]:
        trace = BossTrace(final_decision="accept", iterations_run=0)
        feedback: CriticFeedback | None = None
        current: EstimationResult | None = None

        for iteration in range(self.max_iterations):
            current = actor(feedback)
            review = critic(current)

            decision = self._decide(review, iterations_left=(self.max_iterations - iteration - 1))
            trace.iterations.append(
                ACBIteration(
                    iteration=iteration,
                    decision_after=decision,
                    critic_verdict=review.verdict,
                    critic_confidence=review.confidence_in_review,
                    issue_summary=[
                        f"[{i.severity}] {i.category} @ {i.field_path}"
                        for i in review.issues[:5]
                    ],
                )
            )
            trace.iterations_run = iteration + 1
            log.info(
                "boss_iteration",
                iteration=iteration,
                decision=decision,
                verdict=review.verdict,
                issues=len(review.issues),
            )

            if decision == "accept":
                trace.final_decision = "accept"
                return current, trace
            if decision == "synthesize":
                trace.final_decision = "synthesize"
                return self._synthesize_fallback(current, review), trace

            feedback = review

        trace.final_decision = "synthesize"
        log.info("boss_iteration_budget_exhausted", iterations=self.max_iterations)
        assert current is not None
        return self._synthesize_fallback(current, feedback), trace

    @staticmethod
    def _decide(review: CriticFeedback, *, iterations_left: int) -> BossDecision:
        if review.verdict == "accept":
            return "accept"
        if review.verdict == "reject":
            return "synthesize"
        if iterations_left > 0:
            return "iterate"
        return "synthesize"

    @staticmethod
    def _synthesize_fallback(
        last_result: EstimationResult,
        last_feedback: CriticFeedback | None,
    ) -> EstimationResult:
        """Annotate the last draft with caveats. Never an empty result."""
        if last_feedback is None or not last_feedback.issues:
            note = "⚠ Open caveats from independent review: (no detail available)\n\n"
            new_summary = (note + last_result.summary)[:1200]
            return last_result.model_copy(update={"summary": new_summary})

        issue_lines = [
            f"- [{issue.severity}] {issue.category} ({issue.field_path}): {issue.description}"
            for issue in last_feedback.issues
        ]
        caveats_block = (
            "⚠ Open caveats from independent review (loop did not fully converge):\n"
            + "\n".join(issue_lines)
            + "\n\n"
        )
        new_summary = (caveats_block + last_result.summary)[:1200]
        reduced_confidence = max(30, last_result.confidence_pct // 2)
        return last_result.model_copy(
            update={
                "summary": new_summary,
                "confidence_pct": reduced_confidence,
            }
        )
