import structlog
from fastapi import APIRouter, HTTPException, Query
from instructor.core import InstructorRetryException
from openai import APIConnectionError, APIStatusError, RateLimitError

from config import get_settings
from guardrails.input import InputGuardrailViolation
from prompts.loader import available_prompt_versions
from schemas.estimation import (
    EstimationDetail,
    EstimationListResponse,
    EstimationRequest,
    EstimationResponse,
)
from services.history import HistoryUnavailable, get_estimation, list_estimations
from services.llm_service import LLMServiceError, estimate

router = APIRouter(prefix="/api/v1", tags=["estimations"])
log = structlog.get_logger()

_CLIENT_LLM_FAILURE = "Could not generate the estimation."
_PROVIDER_ERRORS = (
    RateLimitError,
    APIConnectionError,
    APIStatusError,
    InstructorRetryException,
)


def _ensure_llm_configured() -> None:
    if get_settings().llm_configured:
        return
    raise HTTPException(
        status_code=503,
        detail="Missing OPENAI_API_KEY and ANTHROPIC_API_KEY",
    )


@router.post("/estimate", response_model=EstimationResponse)
def create_estimation(
    request: EstimationRequest,
    prompt_version: str = Query("v1"),
) -> EstimationResponse:
    """Render the versioned prompt pair and return a structured estimation."""
    known = available_prompt_versions()
    if prompt_version not in known:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown prompt version {prompt_version!r}. Available: {', '.join(known)}",
        )
    _ensure_llm_configured()
    try:
        return estimate(request, version=prompt_version)
    except InputGuardrailViolation as exc:
        log.info(
            "estimation_blocked_by_input_guardrail",
            reason=exc.reason,
            message=exc.message,
        )
        raise HTTPException(
            status_code=400,
            detail={"reason": exc.reason, "message": exc.message},
        ) from exc
    except (*_PROVIDER_ERRORS, LLMServiceError) as exc:
        log.exception("llm_provider_failed")
        raise HTTPException(status_code=502, detail=_CLIENT_LLM_FAILURE) from exc


@router.get("/estimations", response_model=EstimationListResponse)
def list_saved_estimations() -> EstimationListResponse:
    """Last 20 successful estimations, newest first. No result in the list."""
    try:
        return EstimationListResponse(items=list_estimations(limit=20))
    except HistoryUnavailable as exc:
        log.warning("history_list_unavailable", error=str(exc)[:200])
        raise HTTPException(
            status_code=503, detail="Estimation history is unavailable"
        ) from exc


@router.get("/estimations/{estimation_id}", response_model=EstimationDetail)
def show_saved_estimation(estimation_id: int) -> EstimationDetail:
    try:
        item = get_estimation(estimation_id)
    except HistoryUnavailable as exc:
        log.warning("history_show_unavailable", error=str(exc)[:200])
        raise HTTPException(
            status_code=503, detail="Estimation history is unavailable"
        ) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Estimation not found")
    return item
