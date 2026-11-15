"""Store tests for ``estimation_runs``. No live Postgres."""

from __future__ import annotations

import pytest

from services import estimation_runs as store


def test_insert_raises_when_database_url_missing(monkeypatch):
    monkeypatch.setattr(store, "get_engine", lambda: None)
    with pytest.raises(store.EstimationRunsUnavailable):
        store.insert(transcript="hello")