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
