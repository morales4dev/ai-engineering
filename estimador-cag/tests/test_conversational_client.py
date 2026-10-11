"""Session estimate seams used by smokes. Ours; Lidr has no 503 on this path."""

from fastapi.testclient import TestClient

from main import app

_FORM = {
    "transcript": "We need a CRM with KYC checks and a small team of two.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}


def test_session_estimate_without_keys_returns_503() -> None:
    """HTTP guard, no fake: no keys → 503. No provider."""
    client = TestClient(app)
    session_id = client.post("/sessions").json()["session_id"]
    response = client.post(f"/sessions/{session_id}/estimate", data=_FORM)
    assert response.status_code == 503
    assert response.json()["detail"] == "Missing OPENAI_API_KEY and ANTHROPIC_API_KEY"


def test_conversational_client_estimate_is_smoke(
    conversational_client, fake_wrapper, monkeypatch
) -> None:
    """smoke: TestClient + FakeLLMWrapper. No provider."""

    def _boom(*_args, **_kwargs):
        raise AssertionError("provider called")

    monkeypatch.setattr("litellm.completion", _boom)
    monkeypatch.setattr("services.llm_wrapper.litellm.completion", _boom)

    client, store = conversational_client
    created = client.post("/sessions")
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]
    store.get(session_id)

    response = client.post(f"/sessions/{session_id}/estimate", data=_FORM)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["summary"] == "Canned CRM build for the sales team."
    assert fake_wrapper.chat_calls
    names = [call["response_model"] for call in fake_wrapper.chat_calls]
    assert "EstimationResult" in names
