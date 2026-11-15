import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scripts import eval_retrieval_s10 as evaluation
from scripts.build_advanced_corpus import DOCS_PATH, TRANSCRIPTS_PATH, _chunks


def test_precision_counts_source_ids_and_budget_fallback():
    chunks = [
        SimpleNamespace(source_id="TR-DEMO-001", budget_id=None),
        SimpleNamespace(source_id=None, budget_id="BUD-2024-006"),
        SimpleNamespace(source_id="unrelated", budget_id=None),
    ]
    assert evaluation.precision_at_k(chunks, {"TR-DEMO-001", "BUD-2024-006"}, 5) == 0.4


def test_evaluation_reports_end_to_end_and_per_query(monkeypatch, tmp_path, capsys):
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({
        "k": 5,
        "queries": [{"id": "Q1", "query": "example", "relevant_budget_ids": ["B1"]}],
    }))
    mock_search = AsyncMock(return_value=SimpleNamespace(
        chunks=[SimpleNamespace(source_id="B1", budget_id="B1")]
    ))
    monkeypatch.setattr(evaluation, "GOLDEN_PATH", golden)
    monkeypatch.setattr(evaluation, "CONFIGS", evaluation.CONFIGS[:1])
    monkeypatch.setattr(evaluation, "get_embedder", lambda: object())
    monkeypatch.setattr(evaluation, "get_reranker", lambda: SimpleNamespace(load=lambda: None))
    monkeypatch.setattr(evaluation, "advanced_retrieve", mock_search)
    asyncio.run(evaluation.main())
    assert mock_search.await_count == 4
    assert "| A | Vector | 0.20 |" in capsys.readouterr().out


def test_golden_collection_ids_are_ingestable():
    encoder = SimpleNamespace(encode=lambda text: text.split())
    golden = json.loads(evaluation.GOLDEN_PATH.read_text())
    actual = set()
    for path, kind, key in (
        (TRANSCRIPTS_PATH, "transcript", "transcript_id"),
        (DOCS_PATH, "technical_doc", "doc_id"),
    ):
        for item in json.loads(path.read_text()):
            chunks = _chunks(encoder, kind=kind, item=item)
            assert chunks and all(chunk.metadata[key] == item[key] for chunk in chunks)
            actual.add(item[key])
    references = {
        source_id
        for query in golden["queries"]
        for source_id in query.get("relevant_source_ids", [])
        if source_id.startswith(("TR-", "DOC-"))
    }
    assert references and references <= actual
