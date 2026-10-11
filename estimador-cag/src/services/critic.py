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

# 32 productive hours × 62.50 EUR/h, same as the estimation / critic prompts.
_DEV_WEEK_EUR = 2_000
_IMBALANCE_THRESHOLD_PCT = 75


def build_critic_facts(result: EstimationResult, metadata: ProjectMetadata) -> dict:
    """Shares and rate band for the critic cheatsheet. No verdicts."""
    total = result.total_cost_eur
    phase_shares = []
    for index, phase in enumerate(result.phases):
        share_pct = round(100 * phase.cost_eur / total, 1) if total else 0.0
        phase_shares.append(
            {
                "index": index,
                "name": phase.name,
                "cost_eur": phase.cost_eur,
                "share_pct": share_pct,
            }
        )
    team_size = metadata.assumed_team_size
    duration_weeks = result.total_duration_weeks
    rate_band_eur = team_size * duration_weeks * _DEV_WEEK_EUR if team_size else None
    delta_vs_band_pct = (
        round(100 * (total - rate_band_eur) / rate_band_eur, 1) if rate_band_eur else None
    )
    return {
        "phase_shares": phase_shares,
        "imbalance_threshold_pct": _IMBALANCE_THRESHOLD_PCT,
        "team_size": team_size,
        "duration_weeks": duration_weeks,
        "dev_week_eur": _DEV_WEEK_EUR,
        "rate_band_eur": rate_band_eur,
        "total_cost_eur": total,
        "delta_vs_band_pct": delta_vs_band_pct,
    }


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
        detail_level: str,
    ) -> CriticFeedback:
        system_prompt, user_message = render_critic_prompt(
            transcript=transcript,
            metadata=metadata,
            tier=tier,
            result=result,
            detail_level=detail_level,
            facts=build_critic_facts(result, metadata),
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
