import structlog
from fastapi import APIRouter, HTTPException, Query
from openai import APIConnectionError, APIStatusError, RateLimitError

from config import get_settings
from prompts.loader import available_prompt_versions
from schemas.estimation import EstimationRequest, EstimationResponse
from services.llm_service import LLMServiceError, estimate

router = APIRouter(prefix="/api/v1", tags=["estimations"])
log = structlog.get_logger()

_CLIENT_LLM_FAILURE = "Could not generate the estimation."
_PROVIDER_ERRORS = (RateLimitError, APIConnectionError, APIStatusError)


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
    """Render the versioned prompt pair and return a free-text estimation."""
    known = available_prompt_versions()
    if prompt_version not in known:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown prompt version {prompt_version!r}. Available: {', '.join(known)}",
        )
    _ensure_llm_configured()
    try:
        return estimate(request, version=prompt_version)
    except (*_PROVIDER_ERRORS, LLMServiceError) as exc:
        log.exception("llm_provider_failed")
        raise HTTPException(status_code=502, detail=_CLIENT_LLM_FAILURE) from exc
