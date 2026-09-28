from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

PreprocessingMode = Literal["none", "inline_cleaning", "two_phase"]
ExampleFormat = Literal["markdown", "json", "narrative"]


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


class EstimationResponse(BaseModel):
    """Free-text estimation plus the prompt version that produced it."""

    text: str = Field(description="Estimation rendered by the LLM as free text.")
    prompt_version: str = Field(description="Identifier of the prompt template used.")


class StructureCheck(BaseModel):
    """Level-1 structural evaluation of the generated estimation."""

    has_title: bool
    has_breakdown_table: bool
    has_totals_section: bool
    has_team_section: bool
    has_duration_section: bool
    declared_total_hours: int | None
    sum_row_hours: int | None
    hours_match: bool | None
    declared_total_cost: float | None
    sum_row_cost: float | None
    cost_match: bool | None
    finish_reason_ok: bool
    score: float
    issues: list[str]


class StreamEstimationRequest(BaseModel):
    """Body for POST /estimate/stream. Still the session 03 transcription contract."""

    transcription: str = Field(
        ...,
        min_length=50,
        max_length=50_000,
        description="Meeting transcription text",
    )
    model: str | None = Field(default=None, description="Override the default model")
    max_tokens: int = Field(default=4000, gt=0, le=16000)
