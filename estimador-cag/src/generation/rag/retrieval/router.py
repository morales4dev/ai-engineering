"""Cascade routing to budget, transcript, or technical-document chunks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

from generation.rag.retrieval.collections import ALL_COLLECTIONS, Collection, match_rules

log = structlog.get_logger()


class RouteClassification(BaseModel):
    targets: list[Collection] = Field(min_length=1, max_length=3)
    reason: str = Field(min_length=1, max_length=300)


@dataclass(frozen=True)
class RoutingDecision:
    targets: list[Collection]
    level: str
    reason: str


_CLASSIFIER_PROMPT = (
    "Route a search query to relevant collections: budget (past quotes, cost and hours), "
    "transcript (what was discussed in client meetings), technical_doc (internal guides, "
    "specifications, APIs). Return one to three targets and a brief reason. Do not invent "
    "collections. Prefer multiple targets only when the query needs distinct source types."
)


async def route(
    query_text: str,
    *,
    explicit: list[Collection] | None = None,
    rules_enabled: bool = True,
    classifier_enabled: bool = True,
    max_targets: int = 3,
    model: str | None = None,
) -> RoutingDecision:
    limit = min(3, max(1, max_targets))
    if explicit:
        targets = list(dict.fromkeys(explicit))[:limit]
        return RoutingDecision(targets, "explicit", "Caller specified collections.")
    if rules_enabled:
        hits = match_rules(query_text)
        if hits:
            targets = hits[:limit]
            return RoutingDecision(
                targets,
                "rules",
                f"Vocabulary matched collections: {', '.join(item.value for item in targets)}.",
            )
    if classifier_enabled:
        try:
            classification = await _classify(query_text, model=model)
            targets = list(dict.fromkeys(classification.targets))[:limit]
            if targets:
                return RoutingDecision(targets, "classifier", classification.reason)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "routing_classifier_failed",
                error_type=type(exc).__name__,
                error=str(exc)[:200],
            )
    return RoutingDecision(
        list(ALL_COLLECTIONS),
        "fallback",
        "No rule or classifier signal; searching all collections.",
    )


async def _classify(query_text: str, *, model: str | None) -> RouteClassification:
    from config import get_settings
    from dependencies import get_llm_wrapper

    result, _meta = await asyncio.to_thread(
        get_llm_wrapper().complete_structured,
        system_prompt=_CLASSIFIER_PROMPT,
        user_message=query_text,
        response_model=RouteClassification,
        model_override=model or get_settings().ROUTER_MODEL,
        max_tokens=800,
    )
    return result
