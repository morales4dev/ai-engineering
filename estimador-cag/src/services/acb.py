"""Actor-Critic-Boss orchestration for the session path.

No ``EstimationService``. Actor drafts are throwaway; one turn is persisted
(enriched transcript + final assistant).
"""

from __future__ import annotations

import structlog

from config import get_settings
from dependencies import get_llm_wrapper, get_openai_client
from guardrails.input import check_input
from guardrails.output import enforce_scope_response
from prompts.loader import render_conversational_prompt
from schemas.acb import ACBResponse
from schemas.critic import CriticFeedback
from schemas.estimation import EstimationRequest, EstimationResult
from services.boss import Boss
from services.critic import Critic
from services.metadata_extractor import update_metadata
from sessions import Session
from sessions.compression import apply_compression
from sessions.tier_resolver import Tier, resolve_tier

log = structlog.get_logger()


def estimate_conversational_acb(
    session: Session,
    request: EstimationRequest,
    *,
    transcript: str,
    version: str,
    tier: Tier | None = None,
) -> ACBResponse:
    """ACB variant. ``transcript`` is already enriched."""
    check_input(transcript, openai_client=get_openai_client())
    wrapper = get_llm_wrapper()
    settings = get_settings()

    resolved_tier, rule = resolve_tier(
        transcript=transcript,
        metadata=session.metadata,
        override=tier,
    )
    session.last_resolved_tier = resolved_tier.value
    session.last_tier_rule = rule

    log.info(
        "estimation_acb_request",
        session_id=session.session_id,
        tier=resolved_tier.value,
        tier_rule=rule,
        transcript_chars=len(transcript),
        prompt_version=version,
    )

    def _actor(critic_feedback: CriticFeedback | None) -> EstimationResult:
        system_prompt, user_message = render_conversational_prompt(
            request,
            version=version,
            description=transcript,
            metadata=session.metadata,
            tier=resolved_tier,
            critic_feedback=critic_feedback,
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(session.history.to_messages_list())
        messages.append({"role": "user", "content": user_message})

        draft, meta = wrapper.complete_structured_chat(
            messages=messages,
            response_model=EstimationResult,
        )
        log.info(
            "acb_actor_draft",
            with_critic_feedback=critic_feedback is not None,
            issues_in_feedback=(
                len(critic_feedback.issues) if critic_feedback is not None else 0
            ),
            confidence_pct=draft.confidence_pct,
            total_cost_eur=draft.total_cost_eur,
            **meta,
        )
        return enforce_scope_response(draft)

    critic = Critic(llm_wrapper=wrapper, model=settings.CRITIC_MODEL)

    def _critic(draft: EstimationResult) -> CriticFeedback:
        return critic.review(
            transcript=transcript,
            metadata=session.metadata,
            tier=resolved_tier,
            result=draft,
        )

    boss = Boss(max_iterations=settings.BOSS_MAX_ITERATIONS)
    final_result, trace = boss.run(actor=_actor, critic=_critic)

    session.history.append(user=transcript, assistant=final_result.model_dump_json())
    apply_compression(
        session.history,
        llm_wrapper=wrapper,
        compression_model=settings.COMPRESSION_MODEL,
        anchor_detection_mode=settings.ANCHOR_DETECTION_MODE,
    )
    session.metadata = update_metadata(
        previous=session.metadata,
        transcript=transcript,
        result=final_result,
        llm_wrapper=wrapper,
        model=settings.METADATA_EXTRACTOR_MODEL,
    )
    return ACBResponse(
        result=final_result,
        prompt_version=version,
        cached=False,
        project_metadata=session.metadata,
        acb=trace,
    )
