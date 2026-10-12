"""Golden eval harness tests."""

from __future__ import annotations

from evals.dataset import load_dataset
from evals.metrics import run_all_metrics
from schemas.estimation import EstimationResult
from tests.conftest import make_canned_result


def test_dataset_loads_with_at_least_15_cases() -> None:
    """unit: load JSON only. No HTTP."""
    cases = load_dataset()
    assert len(cases) >= 15
    assert any(c.expected_out_of_scope for c in cases)


def test_run_against_fake_wrapper_collects_metrics_per_case(
    conversational_client, fake_wrapper
) -> None:
    """smoke: TestClient + FakeLLMWrapper. No provider."""
    fake_wrapper.add_turn(
        result=make_canned_result(total_cost_eur=30_000, total_duration_weeks=8)
    )
    client, _store = conversational_client
    cases = load_dataset()[:2]
    for case in cases:
        sid = client.post("/sessions").json()["session_id"]
        form = {
            "transcript": case.transcript,
            "project_type": case.project_type,
            "detail_level": case.detail_level,
            "output_format": case.output_format,
        }
        response = client.post(f"/sessions/{sid}/estimate", data=form)
        assert response.status_code == 200, response.text
        payload = response.json()
        result = EstimationResult.model_validate(payload["result"])
        results = run_all_metrics(case, result)
        assert len(results) == 3
        assert all(
            r.name in {"schema_adherence", "cost_bounds", "content_recall"}
            for r in results
        )
