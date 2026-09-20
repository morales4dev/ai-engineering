import structlog
from fastapi import APIRouter, HTTPException

from schemas.estimation import EstimationRequest, EstimationResponse
from services.llm_service import LLMServiceError, estimate

router = APIRouter(prefix="/api/v1", tags=["estimations"])
log = structlog.get_logger()


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(request: EstimationRequest) -> EstimationResponse:
    """Receive a meeting transcription and return a software project estimation."""
    try:
        return estimate(request)
    except LLMServiceError as exc:
        log.error("estimation_endpoint_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
