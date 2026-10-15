"""smoke: TestClient. No provider. No Postgres."""
from __future__ import annotations

import textwrap
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from dependencies import (
    get_catalog,
    get_filesystem_loader,
    get_parser_registry,
)
from ingestion.catalog.loader import load_catalog
from ingestion.loaders.filesystem import FileSystemLoader
from ingestion.parsers.registry import default_registry
from main import app
from persistence.database import get_session


class _InMemoryJob:
    def __init__(self, source_name: str):
        self.job_id = uuid.uuid4()
        self.source_name = source_name
        self.status = "pending"
        self.documents_count = 0
        self.error_message = None
        self.started_at = datetime.now(timezone.utc)
        self.finished_at = None


class _InMemoryJobsRepo:
    """Module-global so the BackgroundTask and the GET endpoint share state."""

    _store: dict[uuid.UUID, _InMemoryJob] = {}

    def __init__(self, session=None) -> None:
        # session is ignored — we never touch Postgres.
        pass

    def create(self, *, source_name: str):
        job = _InMemoryJob(source_name)
        self._store[job.job_id] = job
        return job

    def get(self, job_id):
        return self._store.get(job_id)

    def mark_running(self, job_id):
        if job := self._store.get(job_id):
            job.status = "running"

    def mark_completed(self, job_id, *, documents_count):
        if job := self._store.get(job_id):
            job.status = "completed"
            job.documents_count = documents_count
            job.finished_at = datetime.now(timezone.utc)

    def mark_failed(self, job_id, *, error_message):
        if job := self._store.get(job_id):
            job.status = "failed"
            job.error_message = error_message
            job.finished_at = datetime.now(timezone.utc)


def _write_minimal_catalog(tmp_path):
    yaml = """
    version: "1.0.0"
    sources:
      - name: tiny_json
        location: budgets
        format: json
        quality: {completeness: 4, consistency: 4, actuality: 5, reliability: 4}
        sensitivity: {has_pii: false, pii_flags: []}
        decision: include
      - name: excluded_xlsx
        location: rate_card.xlsx
        format: xlsx
        quality: {completeness: 4, consistency: 5, actuality: 1, reliability: 4}
        sensitivity: {has_pii: false, pii_flags: []}
        decision: exclude
        decision_reason: "actuality=1 — outdated"
    """
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(textwrap.dedent(yaml), encoding="utf-8")

    budgets_dir = tmp_path / "budgets"
    budgets_dir.mkdir()
    (budgets_dir / "BUDGET-2024-0001.json").write_text(
        '{"budget_id":"BUDGET-2024-0001","currency":"EUR",'
        '"total_amount":100,"signed_at":"2024-01-01","phases":[]}',
        encoding="utf-8",
    )
    return catalog_path


@pytest.fixture
def ingestion_client(tmp_path, monkeypatch):
    catalog_path = _write_minimal_catalog(tmp_path)

    catalog = load_catalog(catalog_path)
    loader = FileSystemLoader(data_root=tmp_path)
    registry = default_registry()

    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_filesystem_loader] = lambda: loader
    app.dependency_overrides[get_parser_registry] = lambda: registry

    def _stub_session():
        yield None

    app.dependency_overrides[get_session] = _stub_session

    monkeypatch.setattr("routers.ingestion.JobsRepository", _InMemoryJobsRepo)

    class _NullSession:
        def close(self):
            pass

    monkeypatch.setattr(
        "routers.ingestion._open_background_session", lambda: _NullSession()
    )

    _InMemoryJobsRepo._store.clear()

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_post_run_returns_202_and_creates_job(ingestion_client):
    response = ingestion_client.post(
        "/api/v1/ingestion/runs", json={"source_name": "tiny_json"}
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["source_name"] == "tiny_json"
    assert "job_id" in body


def test_get_job_reflects_completed_state(ingestion_client):
    # TestClient runs BackgroundTasks synchronously after the response.
    response = ingestion_client.post(
        "/api/v1/ingestion/runs", json={"source_name": "tiny_json"}
    )
    job_id = response.json()["job_id"]
    get = ingestion_client.get(f"/api/v1/ingestion/jobs/{job_id}")
    assert get.status_code == 200
    body = get.json()
    assert body["status"] == "completed"
    assert body["documents_count"] >= 1


def test_unknown_source_returns_404(ingestion_client):
    response = ingestion_client.post(
        "/api/v1/ingestion/runs", json={"source_name": "does_not_exist"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "unknown_source"


def test_excluded_source_returns_400(ingestion_client):
    response = ingestion_client.post(
        "/api/v1/ingestion/runs", json={"source_name": "excluded_xlsx"}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["reason"] == "source_not_included"
    assert detail["decision"] == "exclude"


def test_get_unknown_job_returns_404(ingestion_client):
    fake = "00000000-0000-0000-0000-000000000000"
    assert ingestion_client.get(f"/api/v1/ingestion/jobs/{fake}").status_code == 404


def test_post_run_without_database_returns_503(tmp_path, monkeypatch):
    catalog = load_catalog(_write_minimal_catalog(tmp_path))
    app.dependency_overrides[get_catalog] = lambda: catalog
    monkeypatch.setattr("persistence.database.get_engine", lambda: None)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ingestion/runs", json={"source_name": "tiny_json"}
            )
        assert response.status_code == 503
        assert response.json()["detail"] == "database is unavailable"
    finally:
        app.dependency_overrides.clear()
