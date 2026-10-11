"""Process-local session store.

This is not ``services.history`` (Postgres log of one-shot /estimate rows) and
not ``sqlalchemy.orm.Session``. Volatility is accepted on purpose: the exercise
is the split between sliding-window history and ``project_metadata``, not
durability. No DB, no Redis. Lost on process restart. Not thread-safe; one
uvicorn worker. Multi-worker would give each process its own dict and break
the conversational guarantee.
"""

from __future__ import annotations

from sessions.models import ConversationHistory, Session


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
