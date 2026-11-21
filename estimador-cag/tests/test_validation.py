"""Unit tests for post-generation validation (Session 9)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from generation.rag.schemas import (
    Estimate,
    SourceCitation,
    SourceReference,
    TaskItem,
    WorkModule,
)
from generation.rag.validation import check_coherence, verify_citations


def _estimate(
    *, source_ids: list[int], component_sources: list[int], confidence="high"
) -> Estimate:
    return Estimate(
        total_engineer_days=20,
        duration_weeks=4,
        modules=[
            WorkModule(
                name="Authentication",
                tasks=[TaskItem(
                    name="Auth", engineer_days=20 if component_sources else None,
                    grounded=bool(component_sources),
                    sources=[SourceReference(
                        chunk_id=str(cid), document_id="BUD-001", evidence="120 hours",
                    ) for cid in component_sources],
                )],
            )
        ],
        sources=[
            SourceCitation(source_id=sid, relevance="primary", used_for="auth")
            for sid in source_ids
        ],
        assumptions=[],
        confidence=confidence,
        reasoning="Derived from retrieved budgets.",
    )


def test_verify_citations_all_valid():
    estimate = _estimate(source_ids=[1, 2], component_sources=[1])
    report = verify_citations(estimate, {"1", "2"})
    assert report.grounded_lines == 1
    assert report.verified_citations == 3
    assert not report.has_dangling


def test_verify_citations_flags_fabricated_ids():
    # cites 99 (top-level) and 42 (inside a component) — neither retrieved.
    estimate = _estimate(source_ids=[1, 99], component_sources=[42])
    report = verify_citations(estimate, {"1", "2"})
    assert report.dangling_citations == ["42", "99"]
    assert report.lines[0].status == "dangling"


def test_verify_citations_no_sources_is_insufficient():
    estimate = _estimate(source_ids=[], component_sources=[])
    report = verify_citations(estimate, {"1"})
    assert report.insufficient_lines == 1
    assert report.lines[0].status == "insufficient"
    assert not report.has_dangling


def test_verify_citations_empty_retrieval_flags_every_cited_id():
    estimate = _estimate(source_ids=[1], component_sources=[2])
    assert verify_citations(estimate, set()).dangling_citations == ["1", "2"]


def test_global_only_dangling_and_mixed_line_counts():
    estimate = _estimate(source_ids=[99, 99], component_sources=[1, 1])
    insufficient = TaskItem(name="Novel scope", grounded=False)
    bad = _estimate(source_ids=[], component_sources=[42]).modules[0].tasks[0]
    estimate.modules[0].tasks.extend([insufficient, bad])
    report = verify_citations(estimate, {"1"})
    assert (report.total_lines, report.grounded_lines, report.dangling_lines,
            report.insufficient_lines, report.verified_citations) == (3, 1, 1, 1, 2)
    assert report.dangling_citations == ["42", "99"]
    assert [line.status for line in report.lines] == ["grounded", "insufficient", "dangling"]


def test_dangling_global_citation_is_visible_without_dangling_lines():
    report = verify_citations(_estimate(source_ids=[99], component_sources=[1]), {"1"})
    assert report.has_dangling
    assert report.dangling_lines == 0


@pytest.mark.parametrize(("grounded", "days", "has_source"), [
    (True, 1, False), (False, None, True), (False, 1, False), (False, 0, False),
])
def test_line_grounding_integrity_rejects_invalid_combinations(grounded, days, has_source):
    with pytest.raises(ValidationError):
        TaskItem(
            name="Auth", engineer_days=days, grounded=grounded,
            sources=[SourceReference(
                chunk_id="1", document_id="BUD-001", evidence="120 hours",
            )] if has_source else [],
        )


def test_check_coherence_insufficient_with_nulls_is_coherent():
    estimate = Estimate(
        total_engineer_days=None,
        duration_weeks=None,
        confidence="insufficient",
        reasoning="no sources",
        insufficient_context_explanation="No relevant budgets retrieved.",
    )
    assert check_coherence(estimate) is True


def test_check_coherence_insufficient_with_numbers_is_incoherent():
    estimate = Estimate(
        total_engineer_days=10,
        duration_weeks=2,
        confidence="insufficient",
        reasoning="contradiction",
        insufficient_context_explanation="",
    )
    assert check_coherence(estimate) is False


def test_check_coherence_non_insufficient_always_true():
    estimate = _estimate(source_ids=[1], component_sources=[1], confidence="low")
    assert check_coherence(estimate) is True
