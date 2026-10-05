import structlog
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from instructor.core import InstructorRetryException
from openai import APIConnectionError, APIStatusError, RateLimitError
from pydantic import BaseModel, Field

from config import get_settings
from dependencies import get_llm_wrapper, get_session_store
from guardrails.input import InputGuardrailViolation
from prompts.loader import available_prompt_versions
from schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    EstimationResponseReloaded,
    OutputFormat,
    ProjectType,
)
from services.attachments import (
    AttachmentExtractionError,
    UnsupportedAttachmentError,
    enrich_transcript,
    extract_text,
)
from services.llm_service import estimate_session_bridge
from services.metadata_extractor import update_metadata
from sessions import SessionNotFoundError

router = APIRouter(prefix="/sessions", tags=["sessions"])
log = structlog.get_logger()

_CLIENT_LLM_FAILURE = "Could not generate the estimation."
_PROVIDER_ERRORS = (
    RateLimitError,
    APIConnectionError,
    APIStatusError,
    InstructorRetryException,
)


class CreateSessionResponse(BaseModel):
    session_id: str = Field(description="UUID identifier for the new conversational session.")


def _ensure_llm_configured() -> None:
    if get_settings().llm_configured:
        return
    raise HTTPException(
        status_code=503,
        detail="Missing OPENAI_API_KEY and ANTHROPIC_API_KEY",
    )


@router.post("", response_model=CreateSessionResponse, status_code=201)
def create_session() -> CreateSessionResponse:
    """Create an empty in-memory session. Lost on process restart."""
    session = get_session_store().create()
    log.info("session_created", session_id=session.session_id)
    return CreateSessionResponse(session_id=session.session_id)


@router.post("/{session_id}/estimate", response_model=EstimationResponseReloaded)
async def estimate_in_session(
    session_id: str,
    transcript: str = Form(..., min_length=20, max_length=2000),
    project_type: ProjectType = Form(...),
    detail_level: DetailLevel = Form(...),
    output_format: OutputFormat = Form(...),
    attachments: list[UploadFile] = File(default_factory=list),
    prompt_version: str = Query("v2"),
) -> EstimationResponseReloaded:
    """Session estimate. Still one-shot LLM (bridge A); metadata is refreshed after."""
    known = available_prompt_versions()
    if prompt_version not in known:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown prompt version {prompt_version!r}. Available: {', '.join(known)}",
        )

    try:
        session = get_session_store().get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc

    settings = get_settings()
    extracted: list[tuple[str, str]] = []
    for upload in attachments or []:
        if not upload.filename:
            continue
        content = await upload.read()
        if not content:
            continue
        try:
            text = extract_text(
                filename=upload.filename,
                content=content,
                max_chars=settings.MAX_ATTACHMENT_CHARS,
            )
        except UnsupportedAttachmentError as exc:
            raise HTTPException(
                status_code=415,
                detail={"reason": "unsupported_attachment", "filename": exc.filename},
            ) from exc
        except AttachmentExtractionError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "reason": "attachment_extraction_failed",
                    "filename": exc.filename,
                    "message": exc.message,
                },
            ) from exc
        if text:
            extracted.append((upload.filename, text))

    enriched = enrich_transcript(transcript=transcript, attachments=extracted)
    log.info(
        "session_estimate_received",
        session_id=session_id,
        transcript_chars=len(transcript),
        enriched_transcript_chars=len(enriched),
        attachment_count=len(extracted),
        prompt_version=prompt_version,
    )

    _ensure_llm_configured()
    request = EstimationRequest(
        description=transcript,
        project_type=project_type,
        detail_level=detail_level,
        output_format=output_format,
    )
    try:
        result = estimate_session_bridge(
            request,
            version=prompt_version,
            description=enriched,
            metadata=session.metadata,
        )
    except InputGuardrailViolation as exc:
        log.info(
            "session_estimate_blocked_by_input_guardrail",
            reason=exc.reason,
            message=exc.message,
        )
        raise HTTPException(
            status_code=400,
            detail={"reason": exc.reason, "message": exc.message},
        ) from exc
    except _PROVIDER_ERRORS as exc:
        log.exception("session_llm_provider_failed")
        raise HTTPException(status_code=502, detail=_CLIENT_LLM_FAILURE) from exc

    session.metadata = update_metadata(
        previous=session.metadata,
        transcript=enriched,
        result=result,
        llm_wrapper=get_llm_wrapper(),
        model=settings.METADATA_EXTRACTOR_MODEL,
    )
    return EstimationResponseReloaded(
        result=result,
        prompt_version=prompt_version,
        cached=False,
        project_metadata=session.metadata,
    )
