"""LiteLLM client for Instructor structured calls."""

from __future__ import annotations

import time
from typing import Any, TypeVar

import instructor
import litellm
import structlog
from pydantic import BaseModel

from services.prompt_boundary import apply_untrusted_boundary

T = TypeVar("T", bound=BaseModel)

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
    """Structured LLM client. Caches live in ``estimate_oneshot()``, not here."""

    def __init__(
        self,
        *,
        openai_api_key: str | None,
        anthropic_api_key: str | None,
        primary_model: str,
        timeout: int,
    ):
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.primary_model = primary_model
        self.timeout = timeout
        self._instructor = instructor.from_litellm(litellm.completion)

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
            result = self._instructor.chat.completions.create(
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
        meta = {
            "model": _normalise_model_name(target_model),
            "provider": _provider_from_model(target_model),
            "latency_ms": latency_ms,
        }
        log.info(
            "llm_structured_call_completed",
            model=meta["model"],
            provider=meta["provider"],
            latency_ms=latency_ms,
        )
        return result, meta

    def _api_key_for(self, model: str) -> str | None:
        if _provider_from_model(model) == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key
