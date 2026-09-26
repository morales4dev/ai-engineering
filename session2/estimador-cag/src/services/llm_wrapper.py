"""LiteLLM-backed wrapper that unifies provider calls behind one `complete()` API.

Timeout and retries come from Settings (`LLM_TIMEOUT` / `LLM_RETRIES`).
The Router tries PRIMARY_MODEL and falls back to FALLBACK_MODEL on failure.
A per-request model override bypasses the Router (no fallback by design).
Cost tracking and streaming come in later bullets.
"""

from __future__ import annotations

import time
from typing import Any

import litellm
import structlog
from litellm import Router

from services.cache import EstimationCache

log = structlog.get_logger()


def _normalise_model_name(model: str) -> str:
    """Strip provider prefixes like ``anthropic/`` that LiteLLM may emit."""
    return model.split("/", 1)[1] if "/" in model else model


def _provider_from_model(model: str) -> str:
    name = _normalise_model_name(model).lower()
    if name.startswith("claude"):
        return "anthropic"
    if name.startswith("gpt") or name.startswith("o1") or name.startswith("o3"):
        return "openai"
    return "unknown"


class LLMWrapper:
    """Unified blocking LLM client. One seam for every non-streaming call."""

    def __init__(
        self,
        *,
        openai_api_key: str | None,
        anthropic_api_key: str | None,
        primary_model: str,
        fallback_model: str,
        timeout: int,
        num_retries: int,
        cache: EstimationCache,
    ):
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.num_retries = num_retries
        self.cache = cache

        self.router = Router(
            model_list=[
                {
                    "model_name": "estimator",
                    "litellm_params": {
                        "model": primary_model,
                        "api_key": self._api_key_for(primary_model),
                        "timeout": timeout,
                    },
                },
                {
                    "model_name": "estimator",
                    "litellm_params": {
                        "model": fallback_model,
                        "api_key": self._api_key_for(fallback_model),
                        "timeout": timeout,
                    },
                },
            ],
            fallbacks=[{"estimator": ["estimator"]}],
            num_retries=num_retries,
        )

    def complete(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model_override: str | None = None,
        max_tokens: int = 4000,
        thinking_budget: int | None = None,
    ) -> dict[str, Any]:
        """Single LLM call with cache and optional fallback."""
        cache_key_model = model_override or self.primary_model
        cache_key = EstimationCache.make_key(
            system_prompt=system_prompt,
            user_message=user_message,
            model=cache_key_model,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
        )
        cached = self.cache.get(cache_key)
        if cached:
            return {**cached, "cache_hit": True}

        model = cache_key_model
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        kwargs = self._build_call_kwargs(
            messages=messages,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            model=model,
        )

        log.info(
            "llm_call_started",
            mode="blocking",
            model=model,
            has_thinking=thinking_budget is not None,
        )
        t0 = time.perf_counter()
        try:
            response = self._dispatch(model_override=model_override, **kwargs)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "llm_call_failed",
                error_type=type(exc).__name__,
                error=str(exc),
                latency_ms=latency_ms,
            )
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        result = self._normalise_response(response, latency_ms=latency_ms)
        log.info(
            "llm_call_completed",
            model=result["model"],
            provider=result["provider"],
            input_tokens=result["usage"]["input_tokens"],
            output_tokens=result["usage"]["output_tokens"],
            latency_ms=latency_ms,
            finish_reason=result["finish_reason"],
        )
        self.cache.set(cache_key, result)
        return {**result, "cache_hit": False}

    def _dispatch(self, *, model_override: str | None, **kwargs: Any) -> Any:
        """Router (with fallback) unless the caller asked for a specific model."""
        if model_override:
            return litellm.completion(
                model=model_override,
                api_key=self._api_key_for(model_override),
                timeout=self.timeout,
                num_retries=self.num_retries,
                **kwargs,
            )
        return self.router.completion(model="estimator", **kwargs)

    def _api_key_for(self, model: str) -> str | None:
        if _provider_from_model(model) == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key

    def _build_call_kwargs(
        self,
        *,
        messages: list[dict],
        max_tokens: int,
        thinking_budget: int | None,
        model: str,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if thinking_budget is None:
            return kwargs

        if _provider_from_model(model) == "anthropic":
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            kwargs["max_tokens"] = max(max_tokens, thinking_budget + 1024)
        else:
            log.warning(
                "thinking_budget_ignored_for_provider",
                provider=_provider_from_model(model),
                model=model,
            )
        return kwargs

    @staticmethod
    def _normalise_response(response: Any, *, latency_ms: int) -> dict[str, Any]:
        choice = response.choices[0]
        finish_reason = (choice.finish_reason or "stop").lower()
        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens) or (
            input_tokens + output_tokens
        )

        model = _normalise_model_name(response.model)
        return {
            "estimation": choice.message.content or "",
            "model": model,
            "provider": _provider_from_model(model),
            "finish_reason": finish_reason,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            "latency_ms": latency_ms,
        }
