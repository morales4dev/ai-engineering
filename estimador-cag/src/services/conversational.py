"""Session-path orchestration: sliding-window history + metadata, no caches.

Replaces the one-shot ``estimate_session_bridge``. The system prompt is
rebuilt each turn from the current ``ProjectMetadata``. History is pairs
only; ``append`` stores, then ``apply_compression`` peels overflow
into anchors or the cumulative summary.
Nothing is written to Postgres.
"""

from __future__ import annotations

import structlog

from config import get_settings
from dependencies import get_llm_wrapper, get_openai_client
from guardrails.input import check_input
from guardrails.output import enforce_scope_response
from prompts.loader import render_conversational_prompt
from schemas.estimation import EstimationRequest, EstimationResponseReloaded, EstimationResult
from services.metadata_extractor import update_metadata
from sessions import Session
from sessions.compression import apply_compression
from sessions.tier_resolver import Tier, resolve_tier

log = structlog.get_logger()


def estimate_conversational(
    session: Session,
    request: EstimationRequest,
    *,
    transcript: str,
    version: str,
    tier: Tier | None = None,
) -> EstimationResponseReloaded:
    """Estimate against the session window. ``transcript`` is already enriched."""
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

    system_prompt, user_message = render_conversational_prompt(
        request,
        version=version,
        description=transcript,
        metadata=session.metadata,
        tier=resolved_tier,
    )
    history = session.history.to_messages_list()
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    log.info(
        "estimation_conversational_request",
        session_id=session.session_id,
        history_pairs=len(history) // 2,
        max_turns=session.history.max_turns,
        metadata_is_empty=session.metadata.is_empty(),
        transcript_chars=len(transcript),
        prompt_version=version,
        resolved_tier=resolved_tier.value,
        tier_rule=rule,
    )

    result, meta = wrapper.complete_structured_chat(
        messages=messages,
        response_model=EstimationResult,
    )
    result = enforce_scope_response(result)
    session.history.append(user=transcript, assistant=result.model_dump_json())
    apply_compression(
        session.history,
        llm_wrapper=wrapper,
        compression_model=settings.COMPRESSION_MODEL,
        anchor_detection_mode=settings.ANCHOR_DETECTION_MODE,
    )
    session.metadata = update_metadata(
        previous=session.metadata,
        transcript=transcript,
        result=result,
        llm_wrapper=wrapper,
        model=settings.METADATA_EXTRACTOR_MODEL,
    )
    log.info(
        "estimation_conversational_generated",
        session_id=session.session_id,
        history_pairs=len(session.history.messages) // 2,
        prompt_version=version,
        confidence_pct=result.confidence_pct,
        total_cost_eur=result.total_cost_eur,
        phases=len(result.phases),
        **meta,
    )
    return EstimationResponseReloaded(
        result=result,
        prompt_version=version,
        cached=False,
        project_metadata=session.metadata,
    )
