import json
from pathlib import Path
from types import SimpleNamespace

import dependencies
from generation.rag.schemas import Budget
from routers import corpus_index


async def test_index_run_records_progress_skips_and_failure(monkeypatch):
    from generation.rag.ingest_service import DuplicateDocumentError

    path = Path(__file__).resolve().parents[1] / "data/task_corpus_contradictions.json"
    documents = [Budget.model_validate(item) for item in json.loads(path.read_text())]
    request = corpus_index.IndexRequest(documents=documents, chunk_type="historical_task")
    updates = []
    monkeypatch.setattr(corpus_index, "_update", lambda job_id, **kwargs: updates.append(kwargs))

    async def stats():
        return {"total_chunks": 2}

    async def exists(_budget_id, _chunk_type):
        return False

    class Ingest:
        async def ingest(self, **kwargs):
            if kwargs["budget"].budget_id == documents[1].budget_id:
                raise DuplicateDocumentError(1)
            return SimpleNamespace(chunks_created=2)

    monkeypatch.setattr(corpus_index, "corpus_stats", stats)
    monkeypatch.setattr(corpus_index, "document_exists", exists)
    await corpus_index._expand("job", request, Ingest())
    assert updates[1] == {"processed": 1, "indexed": 1, "skipped": 0, "chunks_created": 2}
    assert updates[2] == {"processed": 2, "indexed": 1, "skipped": 1, "chunks_created": 2}
    assert updates[3]["status"] == "completed"
    assert updates[3]["after_stats"] == {"total_chunks": 2}

    class Broken:
        async def ingest(self, **_kwargs):
            raise RuntimeError("embedding failed")

    updates.clear()
    await corpus_index._expand("job", request, Broken())
    assert updates[-1]["status"] == "failed"
    assert "embedding failed" in updates[-1]["error_message"]


async def test_existing_budget_id_is_skipped_before_embedding(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "data/task_corpus_contradictions.json"
    document = Budget.model_validate(json.loads(path.read_text())[0])
    request = corpus_index.IndexRequest(documents=[document])
    updates = []
    monkeypatch.setattr(corpus_index, "_update", lambda job_id, **kwargs: updates.append(kwargs))

    async def exists(budget_id, chunk_type):
        assert (budget_id, chunk_type) == (document.budget_id, "budget_component")
        return True

    async def stats():
        return {"total_chunks": 1}

    class Ingest:
        async def ingest(self, **kwargs):
            raise AssertionError("A duplicate must not be embedded")

    monkeypatch.setattr(corpus_index, "document_exists", exists)
    monkeypatch.setattr(corpus_index, "corpus_stats", stats)
    await corpus_index._expand("job", request, Ingest())
    assert updates[1]["processed"] == updates[1]["skipped"] == 1
    assert updates[1]["indexed"] == 0


def test_index_http_requires_key_and_validates_before_scheduling(monkeypatch):
    import uuid
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient

    from main import app
    from persistence.database import get_session
    from routers import security

    updates = []
    path = Path(__file__).resolve().parents[1] / "data/task_corpus_contradictions.json"
    document = json.loads(path.read_text())[0]

    class Session:
        def add(self, row):
            self.row = row
            row.job_id = uuid.uuid4()
            row.created_at = datetime.now(UTC)

        def commit(self):
            pass

        def refresh(self, row):
            pass

    class Ingest:
        async def ingest(self, **kwargs):
            return SimpleNamespace(chunks_created=2)

    async def stats():
        return {"total_chunks": 0, "collections": [], "hnsw_indexed": False}

    async def exists(*args):
        return False

    monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(ESTIMATE_API_KEY="key"))
    monkeypatch.setattr(corpus_index, "corpus_stats", stats)
    monkeypatch.setattr(corpus_index, "document_exists", exists)
    monkeypatch.setattr(corpus_index, "_update", lambda job_id, **kwargs: updates.append(kwargs))
    app.dependency_overrides[get_session] = lambda: Session()
    app.dependency_overrides[dependencies.get_rag_ingest_service] = lambda: Ingest()
    try:
        client = TestClient(app)
        assert client.post("/embeddings/index/runs", json={"documents": [document]}).status_code == 401
        response = client.post(
            "/embeddings/index/runs", headers={"X-API-Key": "key"},
            json={"documents": [{"budget_id": "invalid"}]},
        )
        assert response.status_code == 422
        assert not updates
        response = client.post(
            "/embeddings/index/runs", headers={"X-API-Key": "key"},
            json={"documents": [document]},
        )
        assert response.status_code == 202
        assert response.json()["total"] == 1
        assert updates[-1]["status"] == "completed"
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(dependencies.get_rag_ingest_service, None)
