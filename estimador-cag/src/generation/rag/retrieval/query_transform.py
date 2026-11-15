"""Bounded query expansion and decomposition for advanced retrieval."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()

DIRECT = "direct"
EXPAND = "expand"
DECOMPOSE = "decompose"


class SubQuery(BaseModel):
    topic: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=1, max_length=2000)


class QueryTransformation(BaseModel):
    subqueries: list[SubQuery] = Field(min_length=1, max_length=4)


@dataclass(frozen=True)
class QueryPlan:
    technique: str
    subqueries: list[SubQuery]


_EXPAND_PROMPT = (
    "Rewrite the search query as a few alternative formulations of the same intent. "
    "Preserve exact product, technology, acronym, and numeric terms; do not add requirements. "
    "Use the same language as the query. Return at most four standalone queries."
)
_DECOMPOSE_PROMPT = (
    "Split the search query into independent searches, one per distinct topic. "
    "Preserve exact product, technology, acronym, and numeric terms; do not invent requirements. "
    "Use the same language as the query. Return at most four standalone queries."
)


def choose_technique(query_text: str) -> str:
    words = len(query_text.split())
    if words < 6:
        return DIRECT
    lowered = query_text.lower()
    connectors = sum(
        lowered.count(token)
        for token in (" and ", " y ", " además ", " ademas ", " plus ")
    ) + query_text.count(",") + query_text.count(";")
    if words >= 25 or connectors >= 2 or sum(query_text.count(mark) for mark in ".!?") >= 2:
        return DECOMPOSE
    return EXPAND


async def transform_query(
    query_text: str,
    *,
    enabled: bool = True,
    model: str | None = None,
    max_subqueries: int = 4,
) -> QueryPlan:
    technique = choose_technique(query_text) if enabled else DIRECT
    if technique == DIRECT:
        return QueryPlan(DIRECT, [SubQuery(topic="original", query=query_text)])

    try:
        result = await _generate(
            query_text,
            system_prompt=_EXPAND_PROMPT if technique == EXPAND else _DECOMPOSE_PROMPT,
            model=model,
        )
        limit = min(4, max(1, max_subqueries))
        unique: list[SubQuery] = []
        seen: set[str] = set()
        for subquery in result.subqueries:
            normalized = subquery.query.strip()
            key = normalized.casefold()
            if not normalized or key in seen:
                continue
            seen.add(key)
            unique.append(SubQuery(topic=subquery.topic.strip() or "topic", query=normalized))
            if len(unique) == limit:
                break
        if not unique:
            raise ValueError("transformer returned no usable sub-queries")
        return QueryPlan(technique, unique)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "query_transform_failed",
            technique=technique,
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        return QueryPlan(DIRECT, [SubQuery(topic="original", query=query_text)])


async def _generate(
    query_text: str, *, system_prompt: str, model: str | None
) -> QueryTransformation:
    from config import get_settings
    from dependencies import get_llm_wrapper

    result, _meta = await asyncio.to_thread(
        get_llm_wrapper().complete_structured,
        system_prompt=system_prompt,
        user_message=query_text,
        response_model=QueryTransformation,
        model_override=model or get_settings().QUERY_TRANSFORM_MODEL,
        max_tokens=1200,
    )
    return result
