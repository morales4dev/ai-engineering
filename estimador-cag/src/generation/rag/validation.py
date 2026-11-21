"""Post-generation checks for grounded estimates (Session 9).

Two independent guards run after the LLM returns an :class:`Estimate`:

* :func:`verify_citations` — every cited chunk id must correspond to a
  chunk that was actually retrieved. Fabricated ids are the classic grounding
  failure and trigger one corrective retry in the orchestrator.
* :func:`check_coherence` — the ``insufficient`` confidence level has a strict
  shape (no numbers, an explanation present); a violation is a malformed
  response, not a valid estimate.
"""

from __future__ import annotations

from generation.rag.schemas import CitationReport, Estimate, LineCitation


def verify_citations(
    estimate: Estimate,
    retrieved_chunk_ids: set[str],
) -> CitationReport:
    """Check chunk membership, not document identity or evidence semantics."""
    lines: list[LineCitation] = []
    verified = 0
    dangling: set[str] = set()
    grounded_lines = dangling_lines = insufficient_lines = 0

    for module in estimate.modules:
        for task in module.tasks:
            cited = [ref.chunk_id for ref in task.sources]
            missing = [cid for cid in cited if cid not in retrieved_chunk_ids]
            verified += len(cited) - len(missing)
            dangling.update(missing)
            if not task.grounded:
                status = "insufficient"
                insufficient_lines += 1
            elif missing:
                status = "dangling"
                dangling_lines += 1
            else:
                status = "grounded"
                grounded_lines += 1
            lines.append(LineCitation(
                module=module.name, component=task.name, status=status,
                cited_chunk_ids=cited, dangling_chunk_ids=missing,
            ))

    for citation in estimate.sources:
        cid = str(citation.source_id)
        if cid in retrieved_chunk_ids:
            verified += 1
        else:
            dangling.add(cid)

    return CitationReport(
        total_lines=len(lines), grounded_lines=grounded_lines,
        dangling_lines=dangling_lines, insufficient_lines=insufficient_lines,
        verified_citations=verified, dangling_citations=sorted(dangling), lines=lines,
    )


def check_coherence(estimate: Estimate) -> bool:
    """Return whether the estimate's confidence level matches its content.

    When ``confidence == "insufficient"``: both numeric totals must be ``None``,
    ``modules`` must be empty, and ``insufficient_context_explanation`` must be
    non-empty. Any other confidence level is always considered coherent here
    (the numeric checks belong to the schema/business rules, not to this guard).
    """
    if estimate.confidence != "insufficient":
        return True
    return (
        estimate.total_engineer_days is None
        and estimate.duration_weeks is None
        and not estimate.modules
        and bool(estimate.insufficient_context_explanation)
    )
