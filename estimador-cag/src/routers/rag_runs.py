"""Wizard ejecución HTTP: ``/v1/estimate/runs``.

Thin transport. Auth, rate limits, request validation, one facade call, HTTP
error mapping. Persistence and pipeline live in ``services.rag_runs``. This
module must not import the amnesiac pipeline — if a handler needs those
functions, the call belongs in the facade.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from generation.rag.errors import RagError
from generation.rag.schemas import (
    CreateRunRequest,
    EstimationRun,
    RunAssembleRequest,
    RunRetrieveFilters,
    RunVerifyRequest,
)
from routers.rate_limiting import limiter
from routers.security import require_estimate_key
from services import rag_runs as facade
from services.estimation_runs import EstimationRunsUnavailable, RunNotFound
from services.rag_runs import RunStepConflict

log = structlog.get_logger()

router = APIRouter(prefix="/v1/estimate", tags=["estimate-runs"])

_AUTH = [Depends(require_estimate_key)]


def _map(exc: Exception) -> HTTPException:
    if isinstance(exc, RunNotFound):
        return HTTPException(status_code=404, detail="Estimation run not found")
    if isinstance(exc, RunStepConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, EstimationRunsUnavailable):
        return HTTPException(
            status_code=503, detail="Estimation run history is unavailable"
        )
    if isinstance(exc, RagError):
        log.error("run_failed", error_type=type(exc).__name__, error=str(exc)[:300])
        return HTTPException(status_code=502, detail="Failed to process estimation run.")
    raise exc


async def _await(coro):
    try:
        return await coro
    except (RunNotFound, RunStepConflict, EstimationRunsUnavailable, RagError) as exc:
        raise _map(exc) from exc


def _sync(fn):
    try:
        return fn()
    except (RunNotFound, RunStepConflict, EstimationRunsUnavailable, RagError) as exc:
        raise _map(exc) from exc


@router.post("/runs", response_model=EstimationRun, dependencies=_AUTH)
@limiter.limit("30/minute")
async def create_run(request: Request, payload: CreateRunRequest) -> EstimationRun:
    return await _await(
        facade.create_run(payload.transcript, idempotency_key=payload.idempotency_key)
    )


@router.get("/runs", response_model=list[EstimationRun], dependencies=_AUTH)
@limiter.limit("60/minute")
def list_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=20),
) -> list[EstimationRun]:
    return _sync(lambda: facade.list_runs(limit=limit))


@router.get("/runs/{run_id}", response_model=EstimationRun, dependencies=_AUTH)
@limiter.limit("60/minute")
def get_run(request: Request, run_id: int) -> EstimationRun:
    run = _sync(lambda: facade.get(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Estimation run not found")
    return run


@router.post("/runs/{run_id}/reformulate", response_model=EstimationRun, dependencies=_AUTH)
@limiter.limit("30/minute")
async def reformulate_run(request: Request, run_id: int) -> EstimationRun:
    return await _await(facade.reformulate(run_id))


@router.post("/runs/{run_id}/retrieve", response_model=EstimationRun, dependencies=_AUTH)
@limiter.limit("60/minute")
async def retrieve_run(
    request: Request,
    run_id: int,
    payload: RunRetrieveFilters = Body(default_factory=RunRetrieveFilters),
) -> EstimationRun:
    return await _await(facade.retrieve(run_id, payload))


@router.post("/runs/{run_id}/assemble", response_model=EstimationRun, dependencies=_AUTH)
@limiter.limit("60/minute")
async def assemble_run(
    request: Request,
    run_id: int,
    payload: RunAssembleRequest = Body(default_factory=RunAssembleRequest),
) -> EstimationRun:
    return await _await(facade.assemble(run_id, payload.max_context_tokens))


@router.post("/runs/{run_id}/generate", response_model=EstimationRun, dependencies=_AUTH)
@limiter.limit("15/minute")
async def generate_run(request: Request, run_id: int) -> EstimationRun:
    return await _await(facade.generate(run_id))


@router.patch("/runs/{run_id}/verify", response_model=EstimationRun, dependencies=_AUTH)
@limiter.limit("60/minute")
async def verify_run(
    request: Request,
    run_id: int,
    payload: RunVerifyRequest,
) -> EstimationRun:
    return await _await(facade.verify(run_id, payload.modules))
