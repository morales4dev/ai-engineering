import structlog
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from instructor.core import InstructorRetryException
from openai import APIConnectionError, APIStatusError, RateLimitError
from pydantic import BaseModel, Field

from config import get_settings
from dependencies import get_session_store
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
from services.conversational import estimate_conversational
from sessions import ProjectMetadata, SessionNotFoundError

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


class SessionInfoResponse(BaseModel):
    session_id: str
    message_count: int
    max_turns: int
    metadata: ProjectMetadata
    anchors_count: int = 0
    summary_chars: int = 0
    last_resolved_tier: str | None = None
    last_tier_rule: str | None = None


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


@router.get("/{session_id}", response_model=SessionInfoResponse)
def get_session(session_id: str) -> SessionInfoResponse:
    """Read-only inspect of the in-memory session. No LLM."""
    try:
        session = get_session_store().get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="session_not_found") from exc
    return SessionInfoResponse(
        session_id=session.session_id,
        message_count=len(session.history.messages),
        max_turns=session.history.max_turns,
        metadata=session.metadata,
        anchors_count=len(session.history.anchors),
        summary_chars=len(session.history.summary or ""),
        last_resolved_tier=session.last_resolved_tier,
        last_tier_rule=session.last_tier_rule,
    )


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
    """Session estimate: sliding-window history + metadata. Caches stay off."""
    known = available_prompt_versions()
    if prompt_version not in known:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown prompt version {prompt_version!r}. Available: {', '.join(known)}",
        )

    try:
        session = get_session_store().get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="session_not_found") from exc

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
        return estimate_conversational(
            session,
            request,
            transcript=enriched,
            version=prompt_version,
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
