"""Cumulative summarizer for evicted conversation turns.

Fail-open: on any LLM error keep the previous summary or ``""``.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from prompts.loader import render_conversation_summary_prompt
from sessions.models import Message

log = structlog.get_logger()


class _SummaryEnvelope(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)


class CumulativeSummarizer:
    def __init__(self, *, llm_wrapper, model: str) -> None:
        self.llm_wrapper = llm_wrapper
        self.model = model

    def summarize(
        self,
        *,
        previous_summary: str | None,
        evicted: list[Message],
    ) -> str:
        """Return the updated cumulative summary.

        On any LLM error we log and return ``previous_summary or ""``.
        """
        if not evicted:
            return previous_summary or ""

        system_prompt, user_message = render_conversation_summary_prompt(
            previous_summary=previous_summary,
            evicted=evicted,
        )

        try:
            envelope, meta = self.llm_wrapper.complete_structured_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_model=_SummaryEnvelope,
                model_override=self.model,
                max_tokens=1000,
                max_retries=1,
            )
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning(
                "summarizer_failed",
                error_type=type(exc).__name__,
                error=str(exc)[:200],
            )
            return previous_summary or ""

        log.info(
            "summarizer_completed",
            evicted_count=len(evicted),
            previous_chars=len(previous_summary or ""),
            new_chars=len(envelope.summary),
            model=meta.get("model"),
            latency_ms=meta.get("latency_ms"),
        )
        return envelope.summary
