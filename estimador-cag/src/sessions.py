"""In-process conversational session state.

This is not ``services.history`` (Postgres log of one-shot /estimate rows) and
not ``sqlalchemy.orm.Session``. Volatility is accepted on purpose: the exercise
is the split between sliding-window history and ``project_metadata``, not
durability. No DB, no Redis. Lost on process restart. Not thread-safe; one
uvicorn worker. Multi-worker would give each process its own dict and break
the conversational guarantee.
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


Role = Literal["user", "assistant"]


class Message(BaseModel):
    """One history entry. The system prompt is not a Message; it is rebuilt
    each turn from the current ``ProjectMetadata`` and never stored here.
    """

    role: Role
    content: str


class ConversationHistory(BaseModel):
    """Sliding window of user+assistant pairs.

    ``max_turns`` counts pairs, not individual messages. Overflow drops the
    oldest pairs so role alternation stays intact. ``to_messages_list`` is the
    array for the LLM call, without a system message.
    """

    max_turns: int = Field(default=6, ge=1)
    messages: list[Message] = Field(default_factory=list)

    def append(self, *, user: str, assistant: str) -> None:
        """Add one turn and trim if the window is exceeded."""
        self.messages.append(Message(role="user", content=user))
        self.messages.append(Message(role="assistant", content=assistant))
        self._trim()

    def to_messages_list(self) -> list[dict[str, str]]:
        """Return ``[{role, content}, …]`` with no system prompt."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def _trim(self) -> None:
        max_messages = self.max_turns * 2
        overflow = len(self.messages) - max_messages
        if overflow <= 0:
            return
        if overflow % 2 != 0:
            overflow += 1
        del self.messages[:overflow]


class ProjectMetadata(BaseModel):
    """Facts about the project under discussion, kept outside the message array.

    Empty on turn 0. Scalars stay optional so a missing fact is valid state.
    """

    project_name: str | None = None
    assumed_team_size: int | None = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = None

    def is_empty(self) -> bool:
        return (
            self.project_name is None
            and self.assumed_team_size is None
            and not self.mentioned_technologies
            and self.agreed_scope is None
        )

    def merge_with(self, update: ProjectMetadata) -> ProjectMetadata:
        """Non-null scalars from ``update`` win; technologies are a
        case-insensitive union that keeps the first spelling seen.
        """
        merged_tech = list(self.mentioned_technologies)
        seen = {tech.lower() for tech in merged_tech}
        for tech in update.mentioned_technologies:
            key = tech.lower()
            if key not in seen:
                merged_tech.append(tech)
                seen.add(key)

        return ProjectMetadata(
            project_name=update.project_name or self.project_name,
            assumed_team_size=update.assumed_team_size or self.assumed_team_size,
            mentioned_technologies=merged_tech,
            agreed_scope=update.agreed_scope or self.agreed_scope,
        )


class Session(BaseModel):
    """One conversational estimation, addressed by ``session_id`` (UUID v4)."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    history: ConversationHistory = Field(default_factory=ConversationHistory)
    metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)


class SessionNotFoundError(KeyError):
    """Raised by ``SessionStore.get`` when the id is unknown."""


class SessionStore:
    """Process-local ``dict`` of sessions. See the module docstring."""

    def __init__(self, *, max_turns: int = 6) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_turns = max_turns

    def create(self) -> Session:
        session = Session(history=ConversationHistory(max_turns=self._max_turns))
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(session_id) from exc

    def __len__(self) -> int:
        return len(self._sessions)
