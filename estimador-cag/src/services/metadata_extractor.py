"""Second-pass LLM call that extracts ``ProjectMetadata`` from each turn.

Runs after the session estimation succeeds. Fail-open: any extractor
failure is logged and the previous metadata is kept. The conversation
must not die because a facts-refresh failed.
"""

from __future__ import annotations

import structlog

from prompts.loader import render_metadata_extraction_prompt
from schemas.estimation import EstimationResult
from services.llm_wrapper import LLMWrapper
from sessions import ProjectMetadata

log = structlog.get_logger()


def update_metadata(
    *,
    previous: ProjectMetadata,
    transcript: str,
    result: EstimationResult,
    llm_wrapper: LLMWrapper,
    model: str,
) -> ProjectMetadata:
    """Run the extractor and return ``previous.merge_with(extracted)``.

    On failure: log + return ``previous``.
    """
    system_prompt, user_message = render_metadata_extraction_prompt(
        transcript=transcript,
        result=result,
        previous=previous,
    )

    try:
        extracted, meta = llm_wrapper.complete_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=ProjectMetadata,
            model_override=model,
            max_tokens=1000,
            max_retries=2,
        )
    except Exception as exc:  # noqa: BLE001 — fail-open
        log.warning(
            "metadata_extraction_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        return previous

    merged = previous.merge_with(extracted)
    log.info(
        "metadata_extraction_completed",
        model=meta["model"],
        latency_ms=meta["latency_ms"],
        project_name=merged.project_name,
        team_size=merged.assumed_team_size,
        tech_count=len(merged.mentioned_technologies),
    )
    return merged
