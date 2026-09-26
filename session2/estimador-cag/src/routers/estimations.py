import asyncio
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from dependencies import get_llm_wrapper
from schemas.estimation import (
    EstimationRequest,
    EstimationResponse,
    StreamEstimationRequest,
)
from services.llm_service import LLMServiceError, build_system_prompt, estimate
from services.llm_wrapper import LLMWrapper

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


@router.post("/estimate/stream")
async def create_estimation_stream(
    request: StreamEstimationRequest,
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EventSourceResponse:
    """SSE endpoint. Tokens via LLMWrapper.complete_stream, then event ``done``.

    Thinner than POST /estimate: default CAG prompt, no two-phase, no validation.
    Cache hit arrives as one ``token`` event. Streamlit does not call this yet.
    """
    system_prompt = build_system_prompt()

    async def event_generator() -> AsyncIterator[dict]:
        loop = asyncio.get_running_loop()
        chunks = wrapper.complete_stream(
            system_prompt=system_prompt,
            user_message=request.transcription,
            model_override=request.model,
            max_tokens=request.max_tokens,
        )

        def _next_chunk() -> str | None:
            try:
                return next(chunks)
            except StopIteration:
                return None
            except Exception as exc:  # noqa: BLE001 — surface as SSE error event
                log.error("estimate_stream_failed", error=str(exc), error_type=type(exc).__name__)
                raise

        try:
            while True:
                chunk = await loop.run_in_executor(None, _next_chunk)
                if chunk is None:
                    break
                if chunk:
                    yield {"event": "token", "data": chunk}
            yield {"event": "done", "data": "[DONE]"}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": str(exc)}

    return EventSourceResponse(event_generator())
