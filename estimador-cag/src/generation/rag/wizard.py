"""Contracts for the structure-and-hours estimation wizard."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from generation.rag.schemas import Confidence, EstimationRun


class StructureTask(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)


class StructureModule(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    tasks: list[StructureTask] = Field(default_factory=list, max_length=100)


class StructureEstimate(BaseModel):
    modules: list[StructureModule] = Field(default_factory=list, max_length=50)
    confidence: Confidence
    reasoning: str
    assumptions: list[str] = Field(default_factory=list)
    insufficient_context_explanation: str | None = None


class WizardRun(EstimationRun):
    workflow_version: Literal["legacy", "s10"] = "legacy"
    structure: dict = Field(default_factory=dict)
    task_hours: dict = Field(default_factory=dict)


class StructureRequest(BaseModel):
    modules: list[StructureModule] = Field(min_length=1, max_length=50)
    top_k: int | None = Field(default=None, ge=1, le=30)
    distance_threshold: float | None = Field(default=None, ge=0, le=2)
    search_mode: Literal["vector", "hybrid"] | None = None
    rerank: bool | None = None

    @model_validator(mode="after")
    def validate_tasks(self):
        names = [module.name for module in self.modules]
        if len(set(names)) != len(names):
            raise ValueError("Module names must be unique.")
        if not any(module.tasks for module in self.modules):
            raise ValueError("At least one task is required.")
        for module in self.modules:
            tasks = [task.name for task in module.tasks]
            if len(set(tasks)) != len(tasks):
                raise ValueError(f"Task names must be unique within module {module.name}.")
        return self


class CostTask(StructureTask):
    estimated_hours: int = Field(ge=0)
    rate_eur_per_hour: int = Field(ge=0)


class CostModule(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    tasks: list[CostTask] = Field(min_length=1, max_length=100)


class VerifyRequest(BaseModel):
    modules: list[CostModule] = Field(min_length=1, max_length=50)


class TaskNeighbor(BaseModel):
    source_id: int
    budget_id: str | None = None
    estimated_hours: int = Field(ge=0)
    distance: float = Field(ge=0, le=2)


class HourRange(BaseModel):
    low: int
    high: int
    reason: str


class TaskHours(BaseModel):
    module: str
    task: str
    estimated_hours: int | None = None
    reliability: float | None = None
    dispersion: float | None = None
    has_match: bool
    neighbors: list[TaskNeighbor] = Field(default_factory=list)
    hours_range: HourRange | None = None


class TaskHoursResponse(BaseModel):
    tasks: list[TaskHours]
