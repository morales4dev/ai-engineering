"""Critic — independent audit of an EstimationResult.

Fail-open: on any LLM error, accept with ``confidence_in_review=0``.
"""

from __future__ import annotations

import structlog

from prompts.loader import render_critic_prompt
from schemas.critic import CriticFeedback
from schemas.estimation import EstimationResult
from sessions import ProjectMetadata
from sessions.tier_resolver import Tier

log = structlog.get_logger()


class Critic:
    def __init__(self, *, llm_wrapper, model: str) -> None:
        self.llm_wrapper = llm_wrapper
        self.model = model

    def review(
        self,
        *,
        transcript: str,
        metadata: ProjectMetadata,
        tier: Tier,
        result: EstimationResult,
    ) -> CriticFeedback:
        system_prompt, user_message = render_critic_prompt(
            transcript=transcript,
            metadata=metadata,
            tier=tier,
            result=result,
        )

        try:
            feedback, meta = self.llm_wrapper.complete_structured_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_model=CriticFeedback,
                model_override=self.model,
                max_tokens=1500,
                max_retries=3,
            )
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning(
                "critic_failed_fallback_accept",
                error_type=type(exc).__name__,
                error=str(exc)[:200],
            )
            return CriticFeedback(verdict="accept", issues=[], confidence_in_review=0)

        log.info(
            "critic_completed",
            verdict=feedback.verdict,
            issue_count=len(feedback.issues),
            confidence=feedback.confidence_in_review,
            model=meta.get("model"),
            latency_ms=meta.get("latency_ms"),
        )
        return feedback
