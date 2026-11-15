import json
from pathlib import Path

from generation.rag.schemas import Budget
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
