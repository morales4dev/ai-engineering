import asyncio
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from openai import APIConnectionError, APIStatusError, RateLimitError
from sse_starlette.sse import EventSourceResponse

from config import get_settings
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
def create_estimation(request: EstimationRequest) -> EstimationResponse:
    """Receive a meeting transcription and return a software project estimation."""
    _ensure_llm_configured()
    try:
        return estimate(request)
    except (*_PROVIDER_ERRORS, LLMServiceError) as exc:
        log.exception("llm_provider_failed")
        raise HTTPException(status_code=502, detail=_CLIENT_LLM_FAILURE) from exc


@router.post("/estimate/stream")
async def create_estimation_stream(
    request: StreamEstimationRequest,
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EventSourceResponse:
    """SSE endpoint. Tokens via LLMWrapper.complete_stream, then event ``done``.

    Thinner than POST /estimate: default CAG prompt, no two-phase, no validation.
    Cache hit arrives as one ``token`` event. ``streamlit_app.py`` calls this over HTTP;
    ``streamlit_inprocess.py`` does not.
    """
    _ensure_llm_configured()
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

        try:
            while True:
                chunk = await loop.run_in_executor(None, _next_chunk)
                if chunk is None:
                    break
                if chunk:
                    yield {"event": "token", "data": chunk}
            yield {"event": "done", "data": "[DONE]"}
        except Exception:
            log.exception("estimate_stream_failed")
            yield {"event": "error", "data": _CLIENT_LLM_FAILURE}

    return EventSourceResponse(event_generator())
