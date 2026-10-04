"""Output guardrail: filter policy on top of the Pydantic validators.

``enforce_scope_response`` never raises. If confidence is low and the summary
is missing the ``Out of scope:`` prefix, it rewrites the result to a single
``Not estimated`` phase with totals 0 / 1.
"""

from __future__ import annotations

import structlog

from schemas.estimation import (
    LOW_CONFIDENCE_THRESHOLD,
    OUT_OF_SCOPE_PREFIX,
    EstimationResult,
    Phase,
)

log = structlog.get_logger()


_NOT_ESTIMATED_PHASE = Phase(
    name="Not estimated",
    duration_weeks=1,
    cost_eur=0,
    summary="Cannot be sized without more information about scope, integrations and team.",
)


def enforce_scope_response(result: EstimationResult) -> EstimationResult:
    """Rewrite a low-confidence result that did not declare it. Never raises."""
    is_low_confidence = result.confidence_pct < LOW_CONFIDENCE_THRESHOLD
    already_marked = result.summary.startswith(OUT_OF_SCOPE_PREFIX)

    if not is_low_confidence or already_marked:
        return result

    log.info(
        "enforce_scope_response_filtering",
        confidence_pct=result.confidence_pct,
        original_summary_chars=len(result.summary),
    )
    new_summary = (
        f"{OUT_OF_SCOPE_PREFIX} not enough information to estimate confidently. "
        f"Original model rationale: {result.summary[:400]}"
    )
    return EstimationResult(
        summary=new_summary[:1200],
        confidence_pct=result.confidence_pct,
        phases=[_NOT_ESTIMATED_PHASE],
        total_duration_weeks=1,
        total_cost_eur=0,
    )
