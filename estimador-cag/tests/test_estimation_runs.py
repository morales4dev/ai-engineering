"""Store tests for ``estimation_runs``. No live Postgres."""

from __future__ import annotations

import pytest

from services import estimation_runs as store


def test_insert_raises_when_database_url_missing(monkeypatch):
    monkeypatch.setattr(store, "get_engine", lambda: None)
    with pytest.raises(store.EstimationRunsUnavailable):
        store.insert(transcript="hello")


def test_clear_downstream_mapping_covers_stale_estimate():
    # Re-running reformulation must wipe retrieval → human verify.
    assert "generation" in store._CLEAR_AFTER["reformulation"]
    assert "adjusted_breakdown" in store._CLEAR_AFTER["reformulation"]
    assert "reformulation" not in store._CLEAR_AFTER["reformulation"]
    # Generate overwrites generation itself; only the human copy is downstream.
    assert store._CLEAR_AFTER["generation"] == ("adjusted_breakdown",)