import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from generation.rag.schemas import Budget
from scripts.s09 import build_task_corpus
from scripts.s09.build_task_corpus import generate_corpus


def test_generated_corpus_is_reproducible_and_valid():
    path = Path(__file__).resolve().parents[1] / "data" / "task_corpus_s10.json"
    corpus = json.loads(path.read_text())
    assert corpus == generate_corpus()
    assert len(corpus) == 60
    assert len({item["client_metadata"]["sector"] for item in corpus}) == 8
    for item in corpus:
        budget = Budget.model_validate(item)
        assert budget.total_estimated_hours == sum(c.estimated_hours for c in budget.components)


@pytest.mark.parametrize("source", ["default", "relative", "absolute", "external"])
def test_ingest_records_the_actual_corpus_path(monkeypatch, tmp_path, source):
    root = Path(__file__).resolve().parents[1]
    contradictions = root / "data/task_corpus_contradictions.json"
    if source == "default":
        args = []
        expected = "data/task_corpus_s10.json"
    elif source == "external":
        external = tmp_path / "corpus.json"
        external.write_text(contradictions.read_text())
        args = ["--out", str(external)]
        expected = str(external)
    else:
        path = (
            Path("data/task_corpus_contradictions.json")
            if source == "relative" else contradictions
        )
        args = ["--out", str(path)]
        expected = "data/task_corpus_contradictions.json"

    requests = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, *, json):
            requests.append(json)
            return SimpleNamespace(status_code=200)

    monkeypatch.chdir(root)
    monkeypatch.setattr(build_task_corpus.httpx, "Client", Client)
    monkeypatch.setattr(
        sys, "argv", ["build_task_corpus.py", "--ingest-only", "--base-url", "http://test", *args],
    )
    build_task_corpus.main()

    assert requests
    for request in requests:
        assert request["source_path"] == f"{expected}::{request['content']['budget_id']}"
