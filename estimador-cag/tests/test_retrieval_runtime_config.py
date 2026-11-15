from types import SimpleNamespace

import fakeredis
from fastapi.testclient import TestClient

from config import get_settings
from dependencies import get_runtime_retrieval_config
from main import app
from routers import security
from services.runtime_config import RuntimeRetrievalConfig


def test_retrieval_settings_require_key_and_control_runtime(monkeypatch):
    settings = SimpleNamespace(
        RETRIEVAL_SEARCH_MODE="vector", RERANKER_ENABLED=False,
        RETRIEVAL_ROUTING_ENABLED=True, QUERY_TRANSFORM_ENABLED=True,
        TEMPORAL_DECAY_ENABLED=False, TASK_HOURS_TOP_K=5,
        TASK_HOURS_DISTANCE_THRESHOLD=0.45, RERANKER_MODEL="test",
        ESTIMATE_API_KEY="estimate", RETRIEVAL_API_KEY="retrieval",
    )
    runtime = RuntimeRetrievalConfig(fakeredis.FakeRedis(decode_responses=True), settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_runtime_retrieval_config] = lambda: runtime
    try:
        client = TestClient(app)
        assert client.get("/api/v1/config/retrieval").status_code == 401
        assert client.put(
            "/api/v1/config/retrieval", headers={"X-API-Key": "retrieval"},
            json={"task_hours_top_k": 8},
        ).status_code == 401
        response = client.put(
            "/api/v1/config/retrieval", headers={"X-API-Key": "estimate"},
            json={"task_hours_top_k": 8, "rerank": True},
        )
        assert response.status_code == 200
        assert runtime.effective_task_hours_top_k() == 8
        assert runtime.effective_rerank() is True
        response = client.put(
            "/api/v1/config/retrieval", headers={"X-API-Key": "estimate"},
            json={"task_hours_top_k": None},
        )
        assert response.status_code == 200
        assert runtime.effective_task_hours_top_k() == 5
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(get_runtime_retrieval_config, None)
