"""Responses function schemas and deterministic estimation tools."""

from __future__ import annotations

import asyncio
import statistics
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from generation.rag.chunk_types import HISTORICAL_TASK


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SearchFilters(ToolArgs):
    sectors: list[str] | None = None
    project_year_min: int | None = None
    project_year_max: int | None = None


class SearchArgs(ToolArgs):
    query: str = Field(min_length=1)
    filters: SearchFilters | None = None


class ComponentInput(ToolArgs):
    name: str = Field(min_length=1)
    reference_amounts: list[float] = Field(description="Historical engineer-hours.")


class CalculateArgs(ToolArgs):
    components: list[ComponentInput] = Field(min_length=1)


class ValidationComponent(ComponentInput):
    estimated_hours: float = Field(ge=0)


class ValidateArgs(ToolArgs):
    components: list[ValidationComponent] = Field(min_length=1)
    total_hours: float = Field(ge=0)


_FILTER_SCHEMA = {
    "type": ["object", "null"],
    "description": "Optional filters; use null to search across all sectors and years.",
    "properties": {
        "sectors": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Client sectors to include, or null.",
        },
        "project_year_min": {"type": ["integer", "null"], "description": "First year, or null."},
        "project_year_max": {"type": ["integer", "null"], "description": "Last year, or null."},
    },
    "required": ["sectors", "project_year_min", "project_year_max"],
    "additionalProperties": False,
}
_COMPONENT_PROPERTIES = {
    "name": {"type": "string", "description": "Name of the component."},
    "reference_amounts": {
        "type": "array",
        "items": {"type": "number"},
        "description": "Recorded engineer-hours from relevant search results, not invented values.",
    },
}
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_budgets",
        "description": (
            "Search historical budget items for ONE project component. Use a focused query "
            "and call separately for each component. Results include scope, identifiers and "
            "recorded engineer-hours; choose relevant references at the right level of scope. "
            "If filters yield nothing, broaden the search rather than inventing hours."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Description of one component."},
                "filters": _FILTER_SCHEMA,
            },
            "required": ["query", "filters"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "calculate_estimate",
        "description": (
            "Calculate all component estimates in engineer-hours using the median of each "
            "component's historical reference hours plus 15% contingency. Empty references "
            "are flagged as unbudgeted, not estimated. Call after searching each component."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": _COMPONENT_PROPERTIES,
                        "required": ["name", "reference_amounts"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["components"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "validate_estimate",
        "description": (
            "Check a calculated estimate for missing references, implausible hours and an "
            "inconsistent total. Pass the calculated hours and the same reference amounts. "
            "Call as the last tool after calculation; fix issues when possible and recalculate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            **_COMPONENT_PROPERTIES,
                            "estimated_hours": {"type": "number"},
                        },
                        "required": ["name", "reference_amounts", "estimated_hours"],
                        "additionalProperties": False,
                    },
                },
                "total_hours": {"type": "number"},
            },
            "required": ["components", "total_hours"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

RetrievalBackend = Callable[[SearchArgs], Awaitable[list[dict[str, Any]]]]


async def real_retrieval(args: SearchArgs) -> list[dict[str, Any]]:
    """Adapt the existing hybrid retriever and reranker to the agent."""
    from config import get_settings
    from dependencies import get_embedder
    from generation.rag.errors import RetrievalError
    from generation.rag.retriever import search_chunks

    embedder = get_embedder()
    if embedder is None:
        raise RetrievalError("Embedding service is not available.")
    settings = get_settings()
    embedding = await asyncio.to_thread(embedder.embed_one, args.query)
    filters = args.filters or SearchFilters()
    result = await search_chunks(
        embedding,
        query_text=args.query,
        search_mode="hybrid",
        rerank=True,
        top_k=settings.RETRIEVAL_TOP_K,
        distance_threshold=settings.RETRIEVAL_DISTANCE_THRESHOLD,
        sectors=filters.sectors,
        project_year_min=filters.project_year_min,
        project_year_max=filters.project_year_max,
        chunk_types=[HISTORICAL_TASK],
    )
    return [
        {
            "id": chunk.id,
            "content": chunk.content,
            "sector": chunk.sector,
            "project_year": chunk.project_year,
            "budget_id": chunk.budget_id,
            "estimated_hours": chunk.estimated_hours,
            "distance": chunk.distance if chunk.has_vector_distance else None,
        }
        for chunk in result.chunks
    ]


async def search_budgets(args: SearchArgs, backend: RetrievalBackend) -> dict[str, Any]:
    items = await backend(args)
    return {
        "items": items,
        "summary": f"{len(items)} historical items returned for {args.query!r}.",
    }


def calculate_estimate(args: CalculateArgs) -> dict[str, Any]:
    breakdown = []
    for component in args.components:
        refs = component.reference_amounts
        if any(value < 0 for value in refs):
            raise ValueError("Reference hours must be non-negative.")
        hours = round(statistics.median(refs) * 1.15, 1) if refs else 0.0
        breakdown.append(
            {
                "name": component.name,
                "reference_amounts": refs,
                "estimated_hours": hours,
                "unbudgeted": not refs,
            }
        )
    total = round(sum(item["estimated_hours"] for item in breakdown), 1)
    return {
        "components": breakdown,
        "total_hours": total,
        "summary": f"Calculated {total} hours across {len(breakdown)} components.",
    }


def validate_estimate(args: ValidateArgs) -> dict[str, Any]:
    issues = []
    for component in args.components:
        refs = component.reference_amounts
        if any(value < 0 for value in refs):
            raise ValueError("Reference hours must be non-negative.")
        if not refs:
            issues.append(f"{component.name}: no historical reference.")
        elif not min(refs) * 0.5 <= component.estimated_hours <= max(refs) * 2:
            issues.append(f"{component.name}: hours outside the reference range.")
    if abs(sum(item.estimated_hours for item in args.components) - args.total_hours) > 0.05:
        issues.append("Total does not match the component sum.")
    if args.total_hours <= 0 or args.total_hours > 20000:
        issues.append("Total is non-positive or exceeds 20000 hours.")
    return {
        "ok": not issues,
        "issues": issues,
        "summary": ("Estimate passed validation." if not issues else "; ".join(issues)),
    }
