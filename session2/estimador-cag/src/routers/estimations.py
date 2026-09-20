import structlog
from fastapi import APIRouter, HTTPException

from schemas.estimation import EstimationRequest, EstimationResponse
from services.evaluation import evaluate_estimation_structure
from services.llm_service import GenerationOptions, LLMServiceError, generate_estimation

router = APIRouter(prefix="/api/v1", tags=["estimations"])
log = structlog.get_logger()


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(request: EstimationRequest) -> EstimationResponse:
    """Receive a meeting transcription and return a software project estimation."""
    opts = GenerationOptions(
        preprocessing=request.preprocessing,
        example_format=request.example_format,
        num_examples=request.num_examples,
        use_examples=request.use_examples,
        model=request.model,
        max_tokens=request.max_tokens,
        thinking_budget=request.thinking_budget,
    )

    try:
        result = generate_estimation(request.transcription, opts)
    except LLMServiceError as exc:
        log.error("estimation_endpoint_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    validation = (
        evaluate_estimation_structure(result["estimation"], result["finish_reason"])
        if request.evaluate
        else None
    )

    estimation_response = EstimationResponse(**result, validation=validation)

    return estimation_response
