"""Persist the guided structure, task-hours and human verification stages."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from generation.rag.observability import log_stage
from generation.rag.query_reformulator import compose_search_text, reformulate_query
from generation.rag.schemas import ReformulationResult
from generation.rag.structure import generate_structure
from generation.rag.task_hours import estimate_tasks
from generation.rag.wizard import CostModule, StructureRequest, WizardRun
from services import estimation_runs as runs_store
from services.estimation_runs import RunNotFound


class RunStepConflict(Exception):
    def __init__(self, run_id: int, need: str) -> None:
        super().__init__(f"estimation run {run_id} is missing {need}")
        self.run_id = run_id
        self.need = need


def _load(run_id: int) -> WizardRun:
    run = runs_store.get(run_id)
    if run is None:
        raise RunNotFound(run_id)
    if run.workflow_version != "s10":
        raise RunStepConflict(run_id, "a session 10 workflow (legacy run is read-only)")
    return run


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


async def create_run(transcript: str, *, idempotency_key: str | None = None) -> WizardRun:
    inserted = runs_store.insert(transcript=transcript, idempotency_key=idempotency_key)
    return await reformulate(inserted.id)


async def reformulate(run_id: int) -> WizardRun:
    run = _load(run_id)
    started = time.perf_counter()
    with log_stage("reformulation", str(run_id)):
        query = await reformulate_query(run.transcript)
        search_text = compose_search_text(query)
    payload = ReformulationResult(query=query, search_text=search_text).model_dump(mode="json")
    return runs_store.update(
        run_id, reformulation=payload, status="reformulated",
        current_step="reformulation", duration_ms=_elapsed_ms(started),
        generation={}, structure={}, task_hours={}, adjusted_breakdown={},
    )


async def generate(run_id: int) -> WizardRun:
    run = _load(run_id)
    if not run.reformulation:
        raise RunStepConflict(run_id, "reformulation")
    query = ReformulationResult.model_validate(run.reformulation).query
    started = time.perf_counter()
    with log_stage("structure", str(run_id)):
        estimate = await generate_structure(query)
    payload = estimate.model_dump(mode="json")
    return runs_store.update(
        run_id,
        generation={"estimate": payload},
        structure={"modules": payload["modules"]},
        task_hours={},
        adjusted_breakdown={},
        status="generated",
        current_step="review",
        duration_ms=_elapsed_ms(started),
    )


async def estimate_hours(run_id: int, request: StructureRequest) -> WizardRun:
    run = _load(run_id)
    if not run.generation:
        raise RunStepConflict(run_id, "generation")
    started = time.perf_counter()
    with log_stage("task_hours", str(run_id)):
        estimates = await estimate_tasks(request)
    modules = [module.model_dump(mode="json") for module in request.modules]
    matches = iter(estimates)
    for module in modules:
        for task in module["tasks"]:
            match = next(matches)
            task.update(
                estimated_hours=match.estimated_hours,
                rate_eur_per_hour=75,
                hours_reliability=match.reliability,
                has_match=match.has_match,
            )
    total_hours = sum(
        task["estimated_hours"] or 0 for module in modules for task in module["tasks"]
    )
    return runs_store.update(
        run_id,
        structure={"modules": [m.model_dump(mode="json") for m in request.modules]},
        task_hours={"tasks": [estimate.model_dump(mode="json") for estimate in estimates]},
        adjusted_breakdown={
            "modules": modules,
            "total_hours": total_hours,
            "total_cost_eur": total_hours * 75,
            "confirmed_at": None,
        },
        status="hours_estimated",
        current_step="hours",
        duration_ms=_elapsed_ms(started),
    )


async def verify(run_id: int, modules: list[CostModule]) -> WizardRun:
    run = _load(run_id)
    if not run.task_hours:
        raise RunStepConflict(run_id, "task hours")
    cleaned = [module.model_dump(mode="json") for module in modules]
    total_hours = sum(t["estimated_hours"] for m in cleaned for t in m["tasks"])
    total_cost = sum(
        t["estimated_hours"] * t["rate_eur_per_hour"] for m in cleaned for t in m["tasks"]
    )
    return runs_store.update(
        run_id,
        adjusted_breakdown={
            "modules": cleaned,
            "total_hours": total_hours,
            "total_cost_eur": total_cost,
            "confirmed_at": datetime.now(UTC).isoformat(),
        },
        status="confirmed",
        current_step="verification",
    )


def get(run_id: int) -> WizardRun:
    return _load(run_id)


def list_runs(limit: int = 20) -> list[WizardRun]:
    return runs_store.list_runs(limit=limit)
