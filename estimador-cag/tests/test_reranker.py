from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from generation.rag.retrieval.reranker import CrossEncoderReranker


def test_reranker_scores_pairs_and_keeps_highest_scoring_candidates(monkeypatch):
    observed = {}

    class FakeCrossEncoder:
        def __init__(self, model_name, *, device):
            observed["model_name"] = model_name
            observed["device"] = device

        def predict(self, pairs):
            observed["pairs"] = pairs
            return [0.2, 0.9]

    fake_module = ModuleType("sentence_transformers")
    fake_module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    candidates = [SimpleNamespace(content="irrelevant"), SimpleNamespace(content="relevant")]
    reranker = CrossEncoderReranker("test-model")
    result = reranker.rerank("project query", candidates, top_n=1)

    assert result == [candidates[1]]
    assert observed == {
        "model_name": "test-model",
        "device": "cpu",
        "pairs": [("project query", "irrelevant"), ("project query", "relevant")],
    }
