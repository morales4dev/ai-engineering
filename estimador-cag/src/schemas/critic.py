"""Structured feedback schema produced by the Critic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


CriticIssueCategory = Literal[
    "hallucination",
    "scope_mismatch",
    "phase_imbalance",
    "missing_assumption",
    "unrealistic_estimate",
    "tier_mismatch",
]


CriticIssueSeverity = Literal["critical", "major", "minor"]


CriticVerdict = Literal["accept", "needs_iteration", "reject"]


class CriticIssue(BaseModel):
    """A single defect flagged by the Critic."""

    category: CriticIssueCategory
    severity: CriticIssueSeverity
    field_path: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=5, max_length=500)
    suggested_fix: str | None = Field(default=None, max_length=300)


class CriticFeedback(BaseModel):
    """Top-level Critic output. The Boss treats this as authoritative."""

    verdict: CriticVerdict
    issues: list[CriticIssue] = Field(default_factory=list, max_length=12)
    confidence_in_review: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def iteration_requires_blocking_issue(self) -> CriticFeedback:
        if self.verdict == "needs_iteration":
            blocking = [i for i in self.issues if i.severity in {"critical", "major"}]
            if not blocking:
                raise ValueError(
                    "verdict 'needs_iteration' requires at least one issue with "
                    "severity in {critical, major}; minor-only issues should accept"
                )
        if self.verdict == "reject" and not self.issues:
            raise ValueError(
                "verdict 'reject' requires at least one issue describing why"
            )
        return self
