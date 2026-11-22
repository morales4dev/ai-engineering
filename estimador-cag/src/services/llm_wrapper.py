"""Shared structured calls through LiteLLM Chat Completions or native Responses."""

from __future__ import annotations

import re
import time
from typing import Any, TypeVar

import instructor
import litellm
import structlog
from litellm.types.llms.openai import ResponsesAPIResponse
from openai.types.responses import ResponseOutputMessage
from openai.types.shared import ReasoningEffort
from pydantic import BaseModel, ValidationError

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

    Dated snapshots share the base model's price row. Undated versioned names
    keep their model version unchanged.
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
    # Session 9 — reasoning models used by the RAG estimation pipeline.
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
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
    return _call_meta(
        target_model=target_model, latency_ms=latency_ms,
        tokens_in=tokens_in, tokens_out=tokens_out,
    )


def _call_meta(
    *, target_model: str, latency_ms: int, tokens_in: int, tokens_out: int,
) -> dict[str, Any]:
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
        reasoning_effort: str | None = None,
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
        # Reasoning models (gpt-5 family) accept ``reasoning_effort``; LiteLLM
        # forwards it and translates ``max_tokens`` to ``max_completion_tokens``.
        extra: dict[str, Any] = {}
        if reasoning_effort is not None:
            extra["reasoning_effort"] = reasoning_effort

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
                **extra,
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

    def complete_structured_responses(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        model_override: str | None = None,
        max_tokens: int = 4000,
        max_attempts: int = 6,
        reasoning_effort: ReasoningEffort = None,
    ) -> tuple[T, dict[str, Any]]:
        """Use native LiteLLM Responses and validate the JSON with Pydantic.

        Token metadata describes the successful response, as with Instructor.
        Failed validation attempts also log their reported usage.
        """
        target_model = model_override or self.primary_model
        log.info(
            "llm_responses_call_started",
            model=target_model, response_model=response_model.__name__,
        )
        t0 = time.perf_counter()
        try:
            if _provider_from_model(target_model) != "openai":
                raise ValueError("Structured Responses calls require an OpenAI model.")
            if not self.openai_api_key:
                raise ValueError("Structured Responses calls require OPENAI_API_KEY.")
            if max_attempts < 1:
                raise ValueError("max_attempts must be at least one.")
            bounded_system, bounded_user = apply_untrusted_boundary(system_prompt, user_message)
            feedback = ""
            for attempt in range(1, max_attempts + 1):
                response = litellm.responses(
                    model=_normalise_model_name(target_model),
                    custom_llm_provider="openai",
                    use_chat_completions_api=False,
                    drop_params=False,
                    stream=False,
                    api_key=self.openai_api_key,
                    timeout=self.timeout,
                    instructions=bounded_system + feedback,
                    input=bounded_user,
                    text_format=response_model,
                    max_output_tokens=max_tokens,
                    reasoning=(
                        {"effort": reasoning_effort}
                        if reasoning_effort is not None else None
                    ),
                )
                if not isinstance(response, ResponsesAPIResponse):
                    raise TypeError("Structured Responses call returned an unexpected response type.")
                if response.status != "completed":
                    raise ValueError(
                        f"Structured Responses output is {response.status}: "
                        f"{response.incomplete_details or response.error}."
                    )
                for item in response.output:
                    body = item if isinstance(item, dict) else item.model_dump()
                    if body.get("type") != "message":
                        continue
                    message = ResponseOutputMessage.model_validate(body)
                    if any(part.type == "refusal" for part in message.content):
                        raise ValueError("Structured Responses output was refused.")
                output_text = response.output_text
                if not output_text.strip():
                    raise ValueError("Structured Responses output has no text to parse.")
                if response.usage is None:
                    raise ValueError("Structured Responses output has no usage metadata.")
                meta = _call_meta(
                    target_model=target_model,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    tokens_in=response.usage.input_tokens,
                    tokens_out=response.usage.output_tokens,
                )
                try:
                    result = response_model.model_validate_json(output_text)
                except ValidationError as exc:
                    log.warning(
                        "llm_responses_validation_failed",
                        **meta, attempt=attempt, max_attempts=max_attempts,
                    )
                    if attempt == max_attempts:
                        raise
                    feedback = (
                        "\n\nCorrect the previous response's validation errors. "
                        "Return a complete response using only the supplied source data:\n"
                        + exc.json(include_input=False, include_url=False)
                    )
                    continue
                log.info("llm_responses_call_completed", **meta, attempts=attempt)
                return result, meta
            raise RuntimeError("Structured Responses attempts ended without a result.")
        except Exception as exc:
            log.error(
                "llm_responses_call_failed",
                model=target_model, error_type=type(exc).__name__, error=str(exc),
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
            raise

    @staticmethod
    def prepare_agent_input(system_prompt: str, transcript: str) -> tuple[str, str]:
        """Bound the transcript once so the same instructions can be reused."""
        return apply_untrusted_boundary(system_prompt, transcript)

    def agent_response(
        self,
        *,
        instructions: str,
        input_items: Any,
        tools: list[dict[str, Any]],
        response_model: type[T],
        model: str,
        reasoning_effort: ReasoningEffort,
        previous_response_id: str | None = None,
        max_tokens: int = 64000,
    ) -> ResponsesAPIResponse:
        """Make one Responses turn; the caller owns the tool loop and its state."""
        target_model = _normalise_model_name(model)
        if _provider_from_model(target_model) != "openai":
            raise ValueError("Agent Responses calls require an OpenAI model.")
        if not self.openai_api_key:
            raise ValueError("Agent Responses calls require OPENAI_API_KEY.")
        started = time.perf_counter()
        try:
            response = litellm.responses(
                model=target_model,
                custom_llm_provider="openai",
                use_chat_completions_api=False,
                drop_params=False,
                stream=False,
                api_key=self.openai_api_key,
                timeout=self.timeout,
                instructions=instructions,
                input=input_items,
                previous_response_id=previous_response_id,
                tools=tools,
                text_format=response_model,
                max_output_tokens=max_tokens,
                reasoning={"effort": reasoning_effort, "summary": "auto"},
                store=True,
            )
            if not isinstance(response, ResponsesAPIResponse):
                raise TypeError("Agent Responses call returned an unexpected response type.")
            if response.status != "completed":
                raise ValueError(
                    f"Agent Responses output is {response.status}: "
                    f"{response.incomplete_details or response.error}."
                )
            for item in response.output:
                body = item if isinstance(item, dict) else item.model_dump()
                if body.get("type") == "message":
                    message = ResponseOutputMessage.model_validate(body)
                    if any(part.type == "refusal" for part in message.content):
                        raise ValueError("Agent Responses output was refused.")
            if response.usage is None:
                raise ValueError("Agent Responses output has no usage metadata.")
            meta = _call_meta(
                target_model=target_model,
                latency_ms=int((time.perf_counter() - started) * 1000),
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
            )
            log.info("llm_agent_response_completed", **meta)
            return response
        except Exception as exc:
            log.error(
                "llm_agent_response_failed",
                model=target_model,
                error_type=type(exc).__name__,
                error=str(exc),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

    def complete_structured_chat(
        self,
        *,
        messages: list[dict[str, str]],
        response_model: type[T],
        model_override: str | None = None,
        max_tokens: int = 4000,
        max_retries: int = 6,
        reasoning_effort: str | None = None,
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
        extra: dict[str, Any] = {}
        if reasoning_effort is not None:
            extra["reasoning_effort"] = reasoning_effort

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
                **extra,
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
