"""Unit tests for query reformulation (Session 9)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import dependencies as deps
from generation.rag import query_reformulator as qr
from generation.rag.errors import ReformulationError
from generation.rag.schemas import EstimationQuery


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    monkeypatch.setattr(
        qr,
        "get_settings",
        lambda: SimpleNamespace(REFORMULATION_MODEL="gpt-5-mini", GENERATION_MAX_TOKENS=32_000),
    )


class FakeWrapper:
    """Records calls. Scripts primary + fallback ``complete_structured``.

    ``complete()`` is present only so a regression that resurrected it would
    be visible: the fallback must not call it.
    """

    def __init__(
        self,
        *,
        structured=None,
        structured_error=None,
        fallback=None,
        fallback_error=None,
    ):
        self._structured = structured
        self._structured_error = structured_error
        self._fallback = fallback
        self._fallback_error = fallback_error
        self.structured_calls: list[dict] = []
        self.complete_calls = 0

    def complete_structured(self, **kwargs):
        self.structured_calls.append(kwargs)
        if len(self.structured_calls) == 1:
            if self._structured_error is not None:
                raise self._structured_error
            return self._structured, {"model": "gpt-5-mini"}
        if self._fallback_error is not None:
            raise self._fallback_error
        return self._fallback, {"model": "gpt-5-mini"}

    def complete(self, **kwargs):
        self.complete_calls += 1
        raise AssertionError("LLMWrapper.complete() must not be used")


async def test_reformulate_query_happy_path(monkeypatch):
    expected = EstimationQuery(
        function="B2B payments marketplace",
        technologies=["Stripe Connect"],
        sector="finance",
        scale="medium",
    )
    fake = FakeWrapper(structured=expected)
    monkeypatch.setattr(deps, "get_llm_wrapper", lambda: fake)

    result = await qr.reformulate_query("long messy transcript ...")

    assert result == expected
    assert len(fake.structured_calls) == 1
    assert fake.structured_calls[0]["response_model"] is EstimationQuery
    assert fake.complete_calls == 0


async def test_reformulate_query_falls_back_to_one_field_rewrite(monkeypatch):
    fake = FakeWrapper(
        structured_error=RuntimeError("schema validation failed"),
        fallback=qr._FallbackRewrite(query="ecommerce storefront with card checkout"),
    )
    monkeypatch.setattr(deps, "get_llm_wrapper", lambda: fake)

    result = await qr.reformulate_query("transcript the model could not structure")

    assert isinstance(result, EstimationQuery)
    assert result.function == "ecommerce storefront with card checkout"
    # Only ``function`` is populated on the degraded path.
    assert result.technologies == []
    assert len(fake.structured_calls) == 2
    assert fake.structured_calls[0]["response_model"] is EstimationQuery
    assert fake.structured_calls[1]["response_model"] is qr._FallbackRewrite
    assert fake.complete_calls == 0


async def test_reformulate_query_raises_when_both_paths_fail(monkeypatch):
    fake = FakeWrapper(
        structured_error=RuntimeError("boom"),
        fallback=qr._FallbackRewrite(query="   "),  # empty rewrite
    )
    monkeypatch.setattr(deps, "get_llm_wrapper", lambda: fake)

    with pytest.raises(ReformulationError):
        await qr.reformulate_query("transcript")
    assert fake.complete_calls == 0


def test_compose_search_text_joins_grounded_fields():
    query = EstimationQuery(
        function="B2B payments marketplace platform",
        technologies=["Stripe Connect", "KYC"],
        sector="healthcare",
        country="Germany",
        regulations=["BaFin"],
    )
    text = qr.compose_search_text(query)

    assert text.startswith("B2B payments marketplace platform")
    assert "with Stripe Connect, KYC" in text
    assert "for healthcare" in text
    assert "in Germany" in text
    assert "BaFin-compliant" in text


def test_compose_search_text_drops_empty_fields():
    query = EstimationQuery(function="simple internal tool")
    assert qr.compose_search_text(query) == "simple internal tool"
