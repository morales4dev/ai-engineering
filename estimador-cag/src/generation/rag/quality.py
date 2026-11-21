"""Context preparation and evidence checks for grounded estimates."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter

import structlog
from pydantic import BaseModel, Field

from generation.rag.schemas import Estimate, HallucinationReport, LineGate, RetrievedChunk

log = structlog.get_logger()
_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:h|hrs|hours)\b", re.IGNORECASE)


def augment_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    compressed = []
    for chunk in chunks:
        scope_prefixes = ("Module:", "Component:", "Description:", "Tech stack:")
        lines = [
            line.strip() for line in chunk.content.splitlines()
            if line.strip() and (
                line.strip().startswith(scope_prefixes)
                or any(ch.isdigit() for ch in line) or "::" in line
            )
        ]
        if not lines:
            lines = [next((line.strip() for line in chunk.content.splitlines() if line.strip()), "")]
        compressed.append(chunk.model_copy(update={"content": "\n".join(lines)}))
    return compressed[::2] + compressed[1::2][::-1]


class Verdict(BaseModel):
    module: str
    component: str
    entailed: bool
    reason: str


class VerdictPanel(BaseModel):
    verdicts: list[Verdict] = Field(default_factory=list)


async def gate_estimate(
    estimate: Estimate, chunks: list[RetrievedChunk], *, tolerance: float, model: str
) -> HallucinationReport:
    """Audit the final estimate against actual supplied sources; disclose judge failures."""
    from dependencies import get_llm_wrapper

    by_id = {str(chunk.id): chunk for chunk in chunks}
    tasks = [(module.name, task) for module in estimate.modules for task in module.tasks]
    names = Counter((module, task.name) for module, task in tasks)
    judge_inputs = []
    problems: dict[tuple[str, str], str] = {}
    for module, task in tasks:
        key = (module, task.name)
        if not task.grounded:
            continue
        if names[key] != 1:
            problems[key] = "Duplicate task name prevents matching the judge verdict."
            continue
        sources = []
        hours = []
        seen_ids: set[str] = set()
        for ref in task.sources:
            chunk = by_id.get(ref.chunk_id)
            if chunk is None or ref.document_id != (chunk.source_id or chunk.budget_id):
                problems[key] = "Citation does not identify a supplied source and document."
                break
            if ref.evidence not in chunk.content:
                problems[key] = "Quoted evidence is not present in the supplied source."
                break
            if ref.chunk_id in seen_ids:
                continue
            seen_ids.add(ref.chunk_id)
            sources.append(chunk.content)
            if chunk.estimated_hours is not None:
                hours.append(float(chunk.estimated_hours))
            else:
                matches = _HOURS.findall(chunk.content)
                if matches:
                    hours.append(float(matches[-1]))
        if key in problems:
            continue
        if hours and task.engineer_days is not None and task.engineer_days > sum(hours) / 8 * (1 + tolerance):
            problems[key] = "Estimated effort exceeds the hours in the cited sources."
            continue
        judge_inputs.append({
            "module": module, "component": task.name, "engineer_days": task.engineer_days,
            "description": task.description, "sources": sources,
        })

    verdicts: dict[tuple[str, str], Verdict] = {}
    judge_error = None
    if judge_inputs:
        try:
            panel, _ = await asyncio.to_thread(
                get_llm_wrapper().complete_structured,
                system_prompt=(
                    "Audit each estimate line against the supplied source text. Return exactly one "
                    "verdict per module and component. Set entailed=false if its effort or scope "
                    "is not supported; do not infer missing evidence."
                ),
                user_message=json.dumps(judge_inputs, ensure_ascii=False),
                response_model=VerdictPanel,
                model_override=model,
            )
            counts = Counter((v.module, v.component) for v in panel.verdicts)
            verdicts = {
                (v.module, v.component): v for v in panel.verdicts
                if counts[(v.module, v.component)] == 1
            }
        except Exception as exc:  # noqa: BLE001
            log.error("hallucination_judge_failed", error=str(exc)[:200])
            judge_error = "Semantic judge unavailable; lines were not semantically verified."

    lines = []
    for module, task in tasks:
        key = (module, task.name)
        verdict = verdicts.get(key)
        if not task.grounded:
            status, reason = "insufficient", None
        elif key in problems:
            status, reason = "degraded", problems[key]
        elif verdict is None:
            status, reason = "unverified", judge_error or "Judge did not return a unique verdict."
        elif not verdict.entailed:
            status, reason = "degraded", verdict.reason
        else:
            status, reason = "grounded", None
        lines.append(LineGate(module=module, component=task.name, status=status, reason=reason))
    return HallucinationReport(lines=lines, judge_error=judge_error)
