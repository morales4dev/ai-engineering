"""In-process conversational session models.

The system prompt is not a ``Message``; it is rebuilt each turn from the
current ``ProjectMetadata`` and never stored here. Eviction is not done
here: ``append`` only stores the pair. The window peel lives in
``sessions.compression.policy``.
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

    ``max_turns`` counts pairs, not individual messages. ``append`` only
    stores the pair. Overflow is peeled by ``CompressionPolicy`` so role
    alternation stays intact. ``to_messages_list`` is the array for the
    LLM call, without a system message.
    """

    max_turns: int = Field(default=6, ge=1)
    messages: list[Message] = Field(default_factory=list)

    def append(self, *, user: str, assistant: str) -> None:
        """Add one turn. Trim / compression are not applied here."""
        self.messages.append(Message(role="user", content=user))
        self.messages.append(Message(role="assistant", content=assistant))

    def to_messages_list(self) -> list[dict[str, str]]:
        """Return ``[{role, content}, …]`` with no system prompt."""
        return [{"role": m.role, "content": m.content} for m in self.messages]


class ProjectMetadata(BaseModel):
    """Facts about the project under discussion, kept outside the message array.

    Empty on turn 0. Scalars stay optional so a missing fact is valid state.
    """

    project_name: str | None = Field(default=None, max_length=120)
    assumed_team_size: int | None = Field(default=None, ge=1, le=50)
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = Field(default=None, max_length=2000)

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
    last_resolved_tier: str | None = None
    last_tier_rule: str | None = None
