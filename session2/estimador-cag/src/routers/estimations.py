from fastapi import APIRouter

from ..config import get_settings
from ..schemas.estimation import EstimationRequest, EstimationResponse
from ..services.llm_service import generate_estimation


router = APIRouter(prefix="/api/v1", tags=["estimations"])
settings = get_settings()


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(request: EstimationRequest) -> EstimationResponse:
	return EstimationResponse(
		estimation=generate_estimation(request.transcription),
		model=settings.LLM_MODEL,
		provider=settings.LLM_PROVIDER,
	)
