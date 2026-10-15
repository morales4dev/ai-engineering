"""unit: in-process objects only. No HTTP. No Postgres."""

from __future__ import annotations

import persistence.database as database
import pytest
from fastapi import HTTPException


def test_module_import_does_not_need_a_url() -> None:
    assert callable(database.get_engine)
    assert database.get_engine.cache_info().currsize == 0


def test_get_session_raises_503_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: type("S", (), {"DATABASE_URL": None})(),
    )
    database.get_engine.cache_clear()
    gen = database.get_session()
    with pytest.raises(HTTPException) as exc:
        next(gen)
    assert exc.value.status_code == 503
    assert exc.value.detail == "database is unavailable"
    assert database.get_engine() is None
