import copy
from pathlib import Path

import pytest

from scripts.eval_generation_s11 import load_report, regression_gate


def test_regression_gate_rejects_bad_scores_and_incompatible_settings():
    baseline = load_report(Path(__file__).resolve().parents[1] / "evals/ragas_baseline_s11.json")
    current = copy.deepcopy(baseline)
    assert regression_gate(current, baseline)
    current["average"]["faithfulness"] = baseline["average"]["faithfulness"] - 0.051
    assert not regression_gate(current, baseline)
    current = copy.deepcopy(baseline)
    current["per_query"][0]["citation_report"]["dangling_citations"] = ["missing"]
    assert not regression_gate(current, baseline)
    current["configuration"]["generation_model"] = "other"
    with pytest.raises(ValueError, match="generation_model"):
        regression_gate(current, baseline)
