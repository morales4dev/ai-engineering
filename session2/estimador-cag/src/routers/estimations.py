from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.config import settings
from src.services import llm_service


router = APIRouter(prefix="/api/v1", tags=["estimations"])


class EstimationRequest(BaseModel):
	transcription: str = Field(
		min_length=1,
		description="Transcripcion de la reunion con el cliente",
	)


class EstimationResponse(BaseModel):
	estimation: str
	model: str
	provider: str


@router.post("/estimate", response_model=EstimationResponse)
def estimate(request: EstimationRequest) -> EstimationResponse:
	return EstimationResponse(
		estimation=llm_service.estimate_meeting(request.transcription),
		model=settings.llm_model,
		provider=settings.llm_provider,
	)
