import hashlib
import json

import structlog

from dependencies import get_cache, get_llm_wrapper, get_openai_client, get_semantic_cache
from guardrails.input import check_input
from guardrails.output import enforce_scope_response
from prompts.loader import render_estimation_prompt
from schemas.estimation import EstimationRequest, EstimationResponse, EstimationResult
from services.history import persist_estimation

log = structlog.get_logger()


def _exact_cache_key(request: EstimationRequest, prompt_version: str, model: str) -> str:
    """SHA-256 of the typed request + prompt version + model. Prefix is v2 on purpose
    so session-3 prompt-hash keys (`estimation:{digest}`) miss instead of colliding.
    """
    payload = json.dumps(
        {
            "description": request.description,
            "project_type": request.project_type.value,
            "detail_level": request.detail_level.value,
            "output_format": request.output_format.value,
            "prompt_version": prompt_version,
            "model": model,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"estimation:v2:{digest}"


def _persist_and_return(
    request: EstimationRequest,
    result: EstimationResult,
    version: str,
    *,
    cached: bool,
) -> EstimationResponse:
    response = EstimationResponse(result=result, prompt_version=version, cached=cached)
    persist_estimation(request, response)
    return response


def estimate_oneshot(request: EstimationRequest, version: str = "v1") -> EstimationResponse:
    """One-shot product path: check_input → caches → LLM → filter → persist."""
    check_input(request.description, openai_client=get_openai_client())

    wrapper = get_llm_wrapper()
    cache = get_cache()
    semantic = get_semantic_cache()
    cache_key = _exact_cache_key(request, version, wrapper.primary_model)
    cached = cache.get(cache_key)
    if cached:
        log.info("estimation_cache_hit", kind="exact", key_prefix=cache_key[:24])
        result = EstimationResult.model_validate(cached)
        return _persist_and_return(request, result, version, cached=True)

    if semantic is not None:
        semantic_hit = semantic.lookup(request, version)
        if semantic_hit is not None:
            log.info("estimation_cache_hit", kind="semantic")
            return _persist_and_return(request, semantic_hit, version, cached=True)

    system_prompt, user_message = render_estimation_prompt(request, version=version)
    result, meta = wrapper.complete_structured(
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=EstimationResult,
    )
    result = enforce_scope_response(result)
    cache.set(cache_key, result.model_dump(mode="json"))
    if semantic is not None:
        semantic.store(request, result, version)
    log.info(
        "estimation_generated",
        prompt_version=version,
        confidence_pct=result.confidence_pct,
        total_cost_eur=result.total_cost_eur,
        phases=len(result.phases),
        **meta,
    )
    return _persist_and_return(request, result, version, cached=False)


def estimate_session_bridge(
    request: EstimationRequest,
    version: str = "v1",
    *,
    description: str | None = None,
) -> EstimationResult:
    """Temporary session path until conversational.py exists.

    Same LLM shape as ``estimate_oneshot`` (system + one user), without cache
    or persist. ``description`` is the enriched transcript for guardrails and
    the prompt; ``request.description`` stays the form field (20–2000).
    """
    text = description if description is not None else request.description
    check_input(text, openai_client=get_openai_client())
    wrapper = get_llm_wrapper()
    system_prompt, user_message = render_estimation_prompt(
        request, version=version, description=text
    )
    result, meta = wrapper.complete_structured(
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=EstimationResult,
    )
    result = enforce_scope_response(result)
    log.info(
        "session_estimation_generated",
        prompt_version=version,
        transcript_chars=len(request.description),
        prompt_description_chars=len(text),
        confidence_pct=result.confidence_pct,
        total_cost_eur=result.total_cost_eur,
        phases=len(result.phases),
        **meta,
    )
    return result
