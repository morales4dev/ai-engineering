"""LiteLLM client for Instructor structured calls."""

from __future__ import annotations

import re
import time
from typing import Any, TypeVar

import instructor
import litellm
import structlog
from pydantic import BaseModel

from services.prompt_boundary import (
    apply_untrusted_boundary,
    apply_untrusted_boundary_to_latest_user,
)
from services.runtime_config import RuntimeModelConfig

T = TypeVar("T", bound=BaseModel)

log = structlog.get_logger()


_DATED_SUFFIX = re.compile(r"-\d{8}$")


def _normalise_model_name(model: str) -> str:
    """Strip provider prefixes like ``anthropic/`` that LiteLLM may emit."""
    return model.split("/", 1)[1] if "/" in model else model


def _catalog_model_name(model: str) -> str:
    """Price-table key: prefix off, then a trailing ``-YYYYMMDD`` snapshot if present.

    ``claude-haiku-4-5-20251001`` and a future ``-20260301`` share one row.
    ``claude-sonnet-4-5`` is untouched (``4-5`` is the version, not a date).
    """
    return _DATED_SUFFIX.sub("", _normalise_model_name(model))


def _provider_from_model(model: str) -> str:
    name = _normalise_model_name(model).lower()
    if name.startswith("claude"):
        return "anthropic"
    if name.startswith("gpt") or name.startswith("o1") or name.startswith("o3"):
        return "openai"
    return "unknown"


# Cost per 1M tokens (USD).
MODEL_COSTS: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
}


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    costs = MODEL_COSTS.get(_catalog_model_name(model)) or {"input": 0.0, "output": 0.0}
    return round((tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000, 6)


def _tokens_from_raw(raw: Any) -> tuple[int, int]:
    """Count tokens billed on this call.

    The provider reports them on ``raw.usage``: how many we sent (``prompt_tokens``)
    and how many it wrote (``completion_tokens``). If that report is missing we
    return 0 and 0 — the call still worked; we just cannot price it.
    """
    usage = getattr(raw, "usage", None)
    tokens_in = getattr(usage, "prompt_tokens", 0) or 0
    tokens_out = getattr(usage, "completion_tokens", 0) or 0
    return int(tokens_in), int(tokens_out)


def _structured_meta(raw: Any, *, target_model: str, latency_ms: int) -> dict[str, Any]:
    tokens_in, tokens_out = _tokens_from_raw(raw)
    model = _normalise_model_name(target_model)
    return {
        "model": model,
        "provider": _provider_from_model(target_model),
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": _estimate_cost(model, tokens_in, tokens_out),
    }


class LLMWrapper:
    """Structured LLM client. Caches live in ``estimate_oneshot()``, not here."""

    def __init__(
        self,
        *,
        openai_api_key: str | None,
        anthropic_api_key: str | None,
        primary_model: str,
        timeout: int,
        runtime_config: RuntimeModelConfig | None = None,
    ):
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        # Settings default: used when no runtime store is wired (tests).
        self._initial_primary_model = primary_model
        self._runtime_config = runtime_config
        self.timeout = timeout
        self._instructor = instructor.from_litellm(litellm.completion)

    @property
    def primary_model(self) -> str:
        """The model every non-overridden call uses, resolved per call so a
        runtime override (Ajustes) takes effect immediately."""
        if self._runtime_config is not None:
            return self._runtime_config.effective("PRIMARY_MODEL")
        return self._initial_primary_model

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        model_override: str | None = None,
        max_tokens: int = 4000,
        max_retries: int = 6,
    ) -> tuple[T, dict[str, Any]]:
        """Call the LLM via Instructor and return ``(model_instance, meta)``.

        Instructor re-prompts up to ``max_retries`` when a Pydantic validator
        raises. Exact/semantic cache get/set stay in ``estimate_oneshot()``.
        """
        target_model = model_override or self.primary_model
        bounded_system, bounded_user = apply_untrusted_boundary(system_prompt, user_message)
        messages = [
            {"role": "system", "content": bounded_system},
            {"role": "user", "content": bounded_user},
        ]

        log.info(
            "llm_structured_call_started",
            model=target_model,
            response_model=response_model.__name__,
        )
        t0 = time.perf_counter()
        try:
            result, raw = self._instructor.chat.completions.create_with_completion(
                model=target_model,
                api_key=self._api_key_for(target_model),
                timeout=self.timeout,
                messages=messages,
                response_model=response_model,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "llm_structured_call_failed",
                error_type=type(exc).__name__,
                error=str(exc),
                latency_ms=latency_ms,
            )
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        meta = _structured_meta(raw, target_model=target_model, latency_ms=latency_ms)
        log.info(
            "llm_structured_call_completed",
            model=meta["model"],
            provider=meta["provider"],
            latency_ms=latency_ms,
            tokens_in=meta["tokens_in"],
            tokens_out=meta["tokens_out"],
            cost_usd=meta["cost_usd"],
        )
        return result, meta

    def complete_structured_chat(
        self,
        *,
        messages: list[dict[str, str]],
        response_model: type[T],
        model_override: str | None = None,
        max_tokens: int = 4000,
        max_retries: int = 6,
    ) -> tuple[T, dict[str, Any]]:
        """Instructor call over a pre-built ``messages`` list.

        ``prompt_boundary`` wraps only the latest user message. Older turns
        are sent as stored. ``complete_structured`` (one-shot) is unchanged.
        """
        target_model = model_override or self.primary_model
        bounded = apply_untrusted_boundary_to_latest_user(messages)

        log.info(
            "llm_structured_chat_started",
            model=target_model,
            response_model=response_model.__name__,
            messages=len(bounded),
        )
        t0 = time.perf_counter()
        try:
            result, raw = self._instructor.chat.completions.create_with_completion(
                model=target_model,
                api_key=self._api_key_for(target_model),
                timeout=self.timeout,
                messages=bounded,
                response_model=response_model,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "llm_structured_chat_failed",
                error_type=type(exc).__name__,
                error=str(exc),
                latency_ms=latency_ms,
            )
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        meta = _structured_meta(raw, target_model=target_model, latency_ms=latency_ms)
        log.info(
            "llm_structured_chat_completed",
            model=meta["model"],
            provider=meta["provider"],
            latency_ms=latency_ms,
            tokens_in=meta["tokens_in"],
            tokens_out=meta["tokens_out"],
            cost_usd=meta["cost_usd"],
        )
        return result, meta

    def _api_key_for(self, model: str) -> str | None:
        if _provider_from_model(model) == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key
