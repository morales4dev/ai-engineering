from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config import get_settings
from dependencies import get_llm_wrapper, get_openai_client, get_session_store
from main import app
from schemas.estimation import EstimationResult
from sessions import ProjectMetadata
from sessions.store import SessionStore


def make_canned_result(
    *,
    total_cost_eur: int = 25_000,
    total_duration_weeks: int = 6,
    confidence_pct: int = 72,
) -> EstimationResult:
    return EstimationResult(
        summary="Canned CRM build for the sales team.",
        confidence_pct=confidence_pct,
        phases=[
            {
                "name": "Discovery",
                "duration_weeks": 1,
                "cost_eur": 5_000,
                "summary": "Scoping workshops + tech spike.",
            },
            {
                "name": "Build",
                "duration_weeks": total_duration_weeks - 1,
                "cost_eur": total_cost_eur - 5_000,
                "summary": "Core build with React + Postgres.",
            },
        ],
        total_duration_weeks=total_duration_weeks,
        total_cost_eur=total_cost_eur,
    )


class FakeLLMWrapper:
    """In-process double of ``LLMWrapper`` for conversational tests.

    Captures every ``complete_structured_chat`` call. Returns scripted
    EstimationResult / ProjectMetadata pairs for the estimation+extractor
    sequence. For any other ``response_model`` (e.g. summary envelopes from
    the compressor, critic feedback from the Boss), it returns a canned
    instance produced by the registered factory or a sensible default.

    Tests can register factories with ``register_response_for(schema, factory)``.
    """

    def __init__(self) -> None:
        self.chat_calls: list[dict] = []
        self.scripted: list[tuple[EstimationResult, ProjectMetadata]] = []
        self._turn = 0
        self._extra_factories: dict[type, callable] = {}

    def add_turn(
        self,
        *,
        result: EstimationResult | None = None,
        metadata: ProjectMetadata | None = None,
    ) -> None:
        self.scripted.append(
            (result or make_canned_result(), metadata or ProjectMetadata())
        )

    def register_response_for(self, schema: type, factory) -> None:
        """Register a factory that produces an instance of ``schema``.

        ``factory`` is a zero-arg callable. Useful when a test pipeline
        triggers a third Pydantic call (summarizer, critic) that the default
        estimation/metadata pair-script doesn't cover.
        """
        self._extra_factories[schema] = factory

    def _default_for(self, schema: type):
        """Best-effort canned instance when no factory is registered."""
        from sessions.compression.anchors import _AnchorClassification
        from sessions.compression.summarizer import _SummaryEnvelope

        if schema is _SummaryEnvelope:
            return _SummaryEnvelope(summary="(canned summary for tests)")
        if schema is _AnchorClassification:
            return _AnchorClassification(is_anchor=False, reason="default")
        return schema()

    def complete_structured_chat(self, *, messages, response_model, **kwargs):
        self.chat_calls.append(
            {
                "messages": messages,
                "response_model": response_model.__name__,
                "kwargs": kwargs,
            }
        )
        meta = {"model": "gpt-4o-mini", "provider": "openai", "latency_ms": 1}

        if response_model is EstimationResult:
            idx = self._turn // 2
            if idx >= len(self.scripted):
                self.scripted.append((make_canned_result(), ProjectMetadata()))
            result, _metadata = self.scripted[idx]
            self._turn += 1
            return result, meta

        if response_model is ProjectMetadata:
            idx = self._turn // 2
            if idx >= len(self.scripted):
                self.scripted.append((make_canned_result(), ProjectMetadata()))
            _result, metadata = self.scripted[idx]
            self._turn += 1
            return metadata, meta

        factory = self._extra_factories.get(response_model)
        if factory is not None:
            return factory(), meta
        return self._default_for(response_model), meta

    def complete_structured(self, *, system_prompt, user_message, response_model, **kwargs):
        # Ours: metadata_extractor uses this; Lidr's extractor uses chat.
        return self.complete_structured_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_model=response_model,
            **kwargs,
        )


@pytest.fixture(autouse=True)
def no_provider_keys():
    """Tests do not see the machine .env keys."""
    settings = get_settings()
    saved = settings.OPENAI_API_KEY, settings.ANTHROPIC_API_KEY
    settings.OPENAI_API_KEY = None
    settings.ANTHROPIC_API_KEY = None
    yield
    settings.OPENAI_API_KEY, settings.ANTHROPIC_API_KEY = saved


@pytest.fixture
def fake_wrapper() -> FakeLLMWrapper:
    return FakeLLMWrapper()


@pytest.fixture
def session_store_factory():
    """Factory so a test can pick its own ``max_turns``."""

    def _factory(*, max_turns: int = 6) -> SessionStore:
        return SessionStore(max_turns=max_turns)

    return _factory


@pytest.fixture
def conversational_client(
    fake_wrapper: FakeLLMWrapper,
    session_store_factory,
    no_provider_keys,
):
    """Wire FastAPI to the fake wrapper and a fresh in-memory store.

    smoke: TestClient + FakeLLMWrapper. No provider.
    """
    store = session_store_factory()
    settings = get_settings()
    previous_key = settings.OPENAI_API_KEY
    # prelude 503s when no keys; dummy key, real wrapper still overridden
    if not settings.llm_configured:
        settings.OPENAI_API_KEY = "sk-smoke-not-a-real-key"

    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_llm_wrapper] = lambda: fake_wrapper
    app.dependency_overrides[get_openai_client] = lambda: None

    with TestClient(app) as c:
        yield c, store

    settings.OPENAI_API_KEY = previous_key
    app.dependency_overrides.clear()
