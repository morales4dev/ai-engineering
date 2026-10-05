import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from dependencies import get_session_store

router = APIRouter(prefix="/sessions", tags=["sessions"])
log = structlog.get_logger()


class CreateSessionResponse(BaseModel):
    session_id: str = Field(description="UUID identifier for the new conversational session.")


@router.post("", response_model=CreateSessionResponse, status_code=201)
def create_session() -> CreateSessionResponse:
    """Create an empty in-memory session. Lost on process restart."""
    session = get_session_store().create()
    log.info("session_created", session_id=session.session_id)
    return CreateSessionResponse(session_id=session.session_id)
