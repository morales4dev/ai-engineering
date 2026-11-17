import pytest
from streamlit.testing.v1 import AppTest

from wizard_ui import _modules


def test_missing_hours_cannot_be_confirmed():
    rows = [{"Module": "Auth", "Task": "Login", "Hours": None, "Rate EUR/h": 75}]
    with pytest.raises(ValueError, match="Hours is required"):
        _modules(rows, cost=True)


def test_confirmation_preserves_zero_hours_and_rate():
    rows = [{"Module": "Auth", "Task": "Login", "Hours": 0, "Rate EUR/h": 0}]
    result = _modules(rows, cost=True)
    assert result[0]["tasks"][0]["estimated_hours"] == 0
    assert result[0]["tasks"][0]["rate_eur_per_hour"] == 0


def test_existing_run_renders_structure_and_cost_editors(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return []

    monkeypatch.setattr("wizard_ui.httpx.request", lambda *args, **kwargs: Response())
    app = AppTest.from_string(
        "from wizard_ui import render_wizard\nrender_wizard('http://test/runs', 'key')"
    )
    app.session_state["rag_run"] = {
        "id": 1, "status": "hours_estimated", "current_step": "hours",
        "transcript": "x" * 100,
        "reformulation": {"query": {"function": "store"}},
        "generation": {"estimate": {"confidence": "medium", "reasoning": "brief"}},
        "structure": {"modules": [{"name": "Auth", "tasks": [{"name": "Login"}]}]},
        "task_hours": {"tasks": [
            {"module": "Auth", "task": "Login", "has_match": False},
        ]},
        "adjusted_breakdown": {"modules": [{"name": "Auth", "tasks": [
            {"name": "Login", "estimated_hours": None, "rate_eur_per_hour": 75},
        ]}]},
    }
    app.run()
    assert not app.exception
    assert any("no matching task" in warning.value for warning in app.warning)
    assert any("Hours is required" in warning.value for warning in app.warning)


def test_grounded_panel_uses_http_and_displays_sources_and_missing_data(monkeypatch):
    import httpx

    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200, request=httpx.Request("POST", url), headers={"X-Request-ID": "req-11"},
            json={
                "confidence": "low", "reasoning": "Partial evidence.",
                "modules": [{"name": "Auth", "tasks": [
                    {"name": "Login", "engineer_days": 2, "grounded": True, "sources": [
                        {"chunk_id": "1", "document_id": "BUD-1", "evidence": "16 hours"},
                    ]},
                    {"name": "Novel scope", "grounded": False, "engineer_days": None},
                ]}],
            },
        )

    monkeypatch.setattr("wizard_ui.httpx.post", post)
    app = AppTest.from_string(
        "from wizard_ui import render_grounded_estimate\n"
        "render_grounded_estimate('http://test/from-transcript', 'key')"
    ).run()
    app.text_area[0].set_value("x" * 100)
    app.button[0].click().run()
    assert not app.exception
    assert calls[0][1]["headers"] == {"X-API-Key": "key"}
    assert calls[0][1]["json"] == {"transcript": "x" * 100}
    text = " ".join(element.value for element in app.markdown)
    assert "Insufficient source data" in text
    assert "Document: BUD-1" in text
    assert app.code[0].value == "16 hours"
    assert any("req-11" in element.value for element in app.caption)
    assert any("Low confidence" in element.value for element in app.warning)
    assert not app.error


def test_grounded_panel_http_error_is_not_an_empty_estimate(monkeypatch):
    import httpx

    monkeypatch.setattr(
        "wizard_ui.httpx.post",
        lambda url, **kwargs: httpx.Response(
            401, request=httpx.Request("POST", url), text="Unauthorized",
        ),
    )
    app = AppTest.from_string(
        "from wizard_ui import render_grounded_estimate\n"
        "render_grounded_estimate('http://test/from-transcript', 'key')"
    ).run()
    app.text_area[0].set_value("x" * 100)
    app.button[0].click().run()
    assert not app.exception
    assert "401" in app.error[0].value
    assert "grounded_rag_result" not in app.session_state
