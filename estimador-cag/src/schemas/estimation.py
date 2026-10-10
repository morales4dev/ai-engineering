from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from sessions import ProjectMetadata


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class EstimationRequest(BaseModel):
    """Typed form payload for POST /estimate."""

    description: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Free-text description of the project to estimate.",
    )
    project_type: ProjectType = Field(description="Coarse-grained project category.")
    detail_level: DetailLevel = Field(description="How deep the estimation should go.")
    output_format: OutputFormat = Field(description="Shape of the rendered estimation.")


OUT_OF_SCOPE_PREFIX = "Out of scope:"
LOW_CONFIDENCE_THRESHOLD = 30


class Phase(BaseModel):
    """One phase in the breakdown of an estimation."""

    name: str = Field(min_length=1, max_length=64)
    duration_weeks: int = Field(ge=1, le=52)
    cost_eur: int = Field(ge=0, le=1_000_000)
    summary: str = Field(min_length=10, max_length=600)


class EstimationResult(BaseModel):
    """Structured estimation. Validators are the rules Instructor re-prompts on.

    ``total_cost_eur`` is overwritten from the phases; the LLM number is ignored.
    """

    summary: str = Field(min_length=10, max_length=1200)
    confidence_pct: int = Field(ge=0, le=100)
    phases: list[Phase] = Field(min_length=1, max_length=8)
    total_duration_weeks: int = Field(ge=1, le=104)
    total_cost_eur: int = Field(ge=0, le=2_000_000)

    @model_validator(mode="after")
    def phases_sum_matches_total(self) -> "EstimationResult":
        # LLM totals are often wrong; phases are the estimate.
        self.total_cost_eur = sum(p.cost_eur for p in self.phases)
        return self

    @model_validator(mode="after")
    def low_confidence_requires_out_of_scope_prefix(self) -> "EstimationResult":
        if self.confidence_pct < LOW_CONFIDENCE_THRESHOLD and not self.summary.startswith(
            OUT_OF_SCOPE_PREFIX
        ):
            raise ValueError(
                f"confidence_pct < {LOW_CONFIDENCE_THRESHOLD} requires summary to "
                f"start with {OUT_OF_SCOPE_PREFIX!r}; refuse the estimation if the "
                f"description is too vague to size"
            )
        return self


class EstimationResponse(BaseModel):
    """Validated result plus the prompt version that produced it."""

    result: EstimationResult
    prompt_version: str = Field(description="Identifier of the prompt template used.")
    cached: bool = False


class EstimationResponseReloaded(BaseModel):
    """Session-path response. Same shape as ``EstimationResponse`` plus metadata.

    ``cached`` is always false on this path. ``project_metadata`` is the
    session facts after the post-estimate extractor (or the previous value
    if extraction failed open).
    """

    result: EstimationResult
    prompt_version: str = Field(description="Identifier of the prompt template used.")
    cached: bool = False
    project_metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)


class EstimationListItem(BaseModel):
    """One row in GET /estimations. No result payload."""

    id: int
    description_preview: str
    project_type: ProjectType
    detail_level: DetailLevel
    output_format: OutputFormat
    prompt_version: str | None
    cached: bool
    created_at: datetime


class EstimationListResponse(BaseModel):
    items: list[EstimationListItem]


class EstimationDetail(EstimationListItem):
    """GET /estimations/{id}. Same list fields plus full description and result."""

    description: str
    result: EstimationResult
